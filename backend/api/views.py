"""HTTP endpoints. Views stay thin: they check input, call a module's service, and return JSON."""

import csv
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.db.models import Avg, Count, Max, OuterRef, Q, Subquery
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.roles import LABELS, capabilities_of, role_of
from audit.models import AuditEvent
from audit.services import record
from ingestion.models import SourceRecord
from ingestion.sync import sync_source
from mdm.models import Customer, FieldCorrection, GoldenField, MatchSuggestion
from mdm.services import build_customers, decide_suggestion
from sources.models import Source
from compliance.models import KycRecord
from compliance.services import ConsentError, record_consent
from stewardship.services import CorrectionError, decide, propose

from .permissions import HasRole, requires
from .serializers import (
    AuditEventSerializer,
    FieldCorrectionSerializer,
    CustomerDetailSerializer,
    CustomerListSerializer,
    MatchSuggestionSerializer,
    SourceSerializer,
)


# ---------- Login ----------

@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request):
    """Sets the csrftoken cookie. The React app calls this once before logging in."""
    return Response({"detail": "ok"})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = str(request.data.get("username", ""))[:150]
    user = authenticate(request, username=username, password=request.data.get("password"))
    if user is None:
        record(request, AuditEvent.LOGIN_FAILED, username=username)
        return Response({"detail": "Wrong username or password."}, status=status.HTTP_400_BAD_REQUEST)
    login(request, user)
    record(request, AuditEvent.LOGIN, user=user)
    return Response(_user_json(user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    record(request, AuditEvent.LOGOUT)
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])  # works without a role, so the screen can say "no role yet"
def me(request):
    return Response(_user_json(request.user))


def _user_json(user):
    role = role_of(user)
    return {
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "is_staff": user.is_staff,
        "role": role,
        "role_label": LABELS.get(role, "No role"),
        "capabilities": capabilities_of(user),
    }


# ---------- Sources (connectors) ----------

class SourceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    viewsets.GenericViewSet):
    """GET /api/sources/, GET|PATCH /api/sources/<code>/, POST /api/sources/<code>/sync/"""

    serializer_class = SourceSerializer
    lookup_field = "code"
    queryset = Source.objects.annotate(record_count=Count("records")).order_by("-trust", "name")

    def get_permissions(self):
        # Everyone with a role may look at sources; only stewards and admins may change or sync them.
        if self.action in ("update", "partial_update", "sync"):
            return [HasRole(), requires("manage_sources")()]
        return [HasRole()]

    def perform_update(self, serializer):
        # Turning a source on or off, or changing its trust, changes golden records and scores.
        source = serializer.save()
        record(self.request, AuditEvent.UPDATE_SOURCE, target=f"source {source.code}",
               changes=dict(self.request.data))
        build_customers()

    @action(detail=True, methods=["post"])
    def sync(self, request, code=None):
        source = self.get_object()
        try:
            synced = sync_source(source.code)
        except (ValueError, RuntimeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        built = build_customers()
        record(request, AuditEvent.SYNC_SOURCE, target=f"source {source.code}", fetched=synced.fetched)
        return Response({
            "fetched": synced.fetched,
            "created": synced.created,
            "updated": synced.updated,
            "customers": built.customers,
            "new_suggestions": built.new_suggestions,
        })


# ---------- Customers ----------

# Same cut-offs as serializers.trust_band().
BAND_FILTERS = {
    "high": Q(trust_score__gte=0.8),
    "medium": Q(trust_score__gte=0.6, trust_score__lt=0.8),
    "low": Q(trust_score__lt=0.6) | Q(trust_score__isnull=True),
}

def customers_with_details():
    """Customers with their name and related rows loaded up front, so serializing a page takes a few queries."""
    golden_name = GoldenField.objects.filter(customer=OuterRef("pk"), field="name").values("value")[:1]
    return Customer.objects.annotate(golden_name=Subquery(golden_name)).prefetch_related(
        "golden_fields__source",
        "golden_fields__source_record",
        "golden_fields__correction",
        "links__source_record__source",
    )


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/customers/?search=&ordering=score|-score|name, GET /api/customers/<id>/"""

    def get_queryset(self):
        qs = customers_with_details()

        search = self.request.query_params.get("search", "").strip()
        if search:
            q = Q(golden_name__icontains=search)
            code = search.upper().removeprefix("C-")
            if code.isdigit():
                q |= Q(id=int(code) - 10000)
            qs = qs.filter(q)

        band = self.request.query_params.get("band")
        if band in BAND_FILTERS:
            qs = qs.filter(BAND_FILTERS[band])

        ordering = {
            "score": ["trust_score", "id"],
            "-score": ["-trust_score", "id"],
            "name": ["golden_name", "id"],
        }.get(self.request.query_params.get("ordering", "score"), ["trust_score", "id"])
        return qs.order_by(*ordering)

    def get_serializer_class(self):
        return CustomerDetailSerializer if self.action == "retrieve" else CustomerListSerializer

    def get_permissions(self):
        if self.action == "export":
            return [HasRole(), requires("export")()]
        if self.action == "propose_correction":
            return [HasRole(), requires("propose_corrections")()]
        if self.action == "reveal":
            return [HasRole(), requires("reveal_identity")()]
        if self.action == "consent":
            return [HasRole(), requires("record_consent")()]
        return [HasRole()]

    @action(detail=True, methods=["post"])
    def consent(self, request, pk=None):
        """POST /api/customers/<id>/consent/  {purpose, status, channel, note}"""
        customer = self.get_object()
        try:
            c = record_consent(customer.pan_hash, request.data.get("purpose"), request.data.get("status"),
                               request.data.get("channel"), request.data.get("note"), request.user.get_username())
        except ConsentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        record(request, AuditEvent.CONSENT, target=customer.code, purpose=c.purpose, status=c.status,
               channel=c.channel)
        return Response({"purpose": c.purpose, "status": c.status}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reveal(self, request, pk=None):
        """POST /api/customers/<id>/reveal/  {field: "pan" | "ckyc", reason}
        Returns the full number once. The reason, who asked and when are written to the audit log."""
        from security.fields import ENCRYPTED_FIELDS, reveal as reveal_value

        customer = self.get_object()
        field = request.data.get("field")
        reason = str(request.data.get("reason", "")).strip()
        if field not in ENCRYPTED_FIELDS:
            return Response({"detail": "Only PAN and CKYC number can be revealed."}, status=status.HTTP_400_BAD_REQUEST)
        if len(reason) < 5:
            return Response({"detail": "Give a reason for viewing the full number."}, status=status.HTTP_400_BAD_REQUEST)
        golden = GoldenField.objects.filter(customer=customer, field=field).first()
        if not golden:
            return Response({"detail": "No value on file."}, status=status.HTTP_404_NOT_FOUND)
        record(request, AuditEvent.REVEAL, target=customer.code, field=field, reason=reason)
        return Response({"field": field, "value": reveal_value(field, golden.value)})

    @action(detail=True, methods=["post"], url_path="corrections")
    def propose_correction(self, request, pk=None):
        """POST /api/customers/<id>/corrections/  {field, value, evidence_ref, reason}"""
        customer = self.get_object()
        try:
            correction = propose(
                customer,
                field=request.data.get("field"),
                value=request.data.get("value"),
                evidence_ref=request.data.get("evidence_ref"),
                reason=request.data.get("reason"),
                user=request.user,
            )
        except CorrectionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        record(request, AuditEvent.CORRECTION_PROPOSED, target=customer.code, field=correction.field,
               evidence=correction.evidence_ref, correction=correction.id)
        return Response(FieldCorrectionSerializer(correction, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        # One entry per user per customer per minute: a page reload is not a second look at the data.
        recent = AuditEvent.objects.filter(
            actor=request.user,
            action=AuditEvent.VIEW_CUSTOMER,
            target=response.data["code"],
            at__gte=timezone.now() - timedelta(minutes=1),
        )
        if not recent.exists():
            record(request, AuditEvent.VIEW_CUSTOMER, target=response.data["code"], masked=response.data["masked"])
        return response

    @action(detail=False, methods=["get"])
    def export(self, request):
        """GET /api/customers/export/ -> CSV of the (filtered) list. Names and scores only, no contact data."""
        rows = self.get_queryset()
        serializer = CustomerListSerializer(rows, many=True, context={"request": request})
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="lumina-customers-{timezone.localdate()}.csv"'
        response.write("\ufeff")  # lets Excel open the file as UTF-8
        writer = csv.writer(response)
        writer.writerow(["Customer ID", "Name", "Trust score", "Band", "Sources", "Fields in conflict",
                         "Fields to review"])
        for c in serializer.data:
            writer.writerow([c["code"], c["name"], c["trust_score"], c["band"], "; ".join(c["sources"]),
                             c["conflict_fields"], c["needs_review"]])
        record(request, AuditEvent.EXPORT, target="customers", rows=len(serializer.data),
               filters=dict(request.query_params))
        return response


# ---------- Match suggestions (steward review) ----------

class MatchSuggestionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/suggestions/?status=pending, POST /api/suggestions/<id>/accept/ or /reject/"""

    serializer_class = MatchSuggestionSerializer

    def get_permissions(self):
        if self.action in ("accept", "reject"):
            return [HasRole(), requires("decide_matches")()]
        return [HasRole(), requires("view_matches")()]

    def get_queryset(self):
        qs = MatchSuggestion.objects.select_related(
            "record_a__source", "record_b__source",
            "record_a__customer_link__customer", "record_b__customer_link__customer",
        )
        wanted = self.request.query_params.get("status")
        return qs.filter(status=wanted) if wanted else qs

    def _decide(self, accept):
        suggestion = self.get_object()
        if suggestion.status != MatchSuggestion.PENDING:
            return Response({"detail": f"Already {suggestion.status}."}, status=status.HTTP_400_BAD_REQUEST)
        decide_suggestion(suggestion, accept=accept)
        record(
            self.request,
            AuditEvent.MERGE if accept else AuditEvent.KEEP_APART,
            target=f"{suggestion.record_a} + {suggestion.record_b}"[:100],
            suggestion=suggestion.id,
        )
        build_customers()
        suggestion.refresh_from_db()
        return Response(self.get_serializer(suggestion).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self._decide(accept=True)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(accept=False)


# ---------- Corrections (maker-checker) ----------

class FieldCorrectionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/corrections/?status=pending&customer=<id>, POST /api/corrections/<id>/approve/ or /reject/"""

    serializer_class = FieldCorrectionSerializer

    def get_permissions(self):
        if self.action in ("approve", "reject"):
            return [HasRole(), requires("approve_corrections")()]
        return [HasRole(), requires("propose_corrections", "approve_corrections")()]

    def get_queryset(self):
        qs = FieldCorrection.objects.select_related("customer").prefetch_related("customer__golden_fields")
        wanted = self.request.query_params.get("status")
        if wanted:
            qs = qs.filter(status=wanted)
        customer = self.request.query_params.get("customer")
        if customer and customer.isdigit():
            qs = qs.filter(customer_id=int(customer))
        return qs

    def _decide(self, approve):
        correction = self.get_object()
        try:
            correction = decide(correction, approve=approve, user=self.request.user,
                                note=self.request.data.get("note", ""))
        except CorrectionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        record(
            self.request,
            AuditEvent.CORRECTION_APPROVED if approve else AuditEvent.CORRECTION_REJECTED,
            target=correction.customer.code,
            field=correction.field,
            correction=correction.id,
            proposed_by=correction.proposed_by_name,
        )
        return Response(self.get_serializer(correction).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(approve=True)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(approve=False)


# ---------- Compliance queue ----------

RISK_ORDER = {"high": 0, "medium": 1, "low": 2}


@api_view(["GET"])
@permission_classes([HasRole, requires("view_compliance")])
def compliance_queue(request):
    """GET /api/compliance/?status=overdue|due_soon|verified|no_record&risk=high|medium|low
    Every customer with KYC and AML status, highest risk and earliest due date first."""
    names = dict(GoldenField.objects.filter(field="name").values_list("customer_id", "value"))
    kyc = {k.pan_hash: k for k in KycRecord.objects.all()}
    rows = []
    for c in Customer.objects.all():
        k = kyc.get(c.pan_hash) if c.pan_hash else None
        rows.append({
            "id": c.id, "code": c.code, "name": names.get(c.id, ""),
            "trust_score": str(c.trust_score) if c.trust_score is not None else None,
            "kyc_status": k.status() if k else "no_record",
            "re_kyc_due": k.re_kyc_due.isoformat() if k else None,
            "last_kyc": k.last_kyc.isoformat() if k else None,
            "risk": k.risk if k else None,
            "risk_reason": k.risk_reason if k else "",
            "pep": k.pep if k else False,
            "sanctions": k.sanctions if k else None,
        })

    counts = {
        "customers": len(rows),
        "overdue": sum(r["kyc_status"] == "overdue" for r in rows),
        "due_soon": sum(r["kyc_status"] == "due_soon" for r in rows),
        "verified": sum(r["kyc_status"] == "verified" for r in rows),
        "no_record": sum(r["kyc_status"] == "no_record" for r in rows),
        "high_risk": sum(r["risk"] == "high" for r in rows),
        "medium_risk": sum(r["risk"] == "medium" for r in rows),
        "low_risk": sum(r["risk"] == "low" for r in rows),
        "pep": sum(r["pep"] for r in rows),
        "sanctions_review": sum(r["sanctions"] == "potential_match" for r in rows),
    }

    wanted_status = request.query_params.get("status")
    wanted_risk = request.query_params.get("risk")
    if wanted_status:
        rows = [r for r in rows if r["kyc_status"] == wanted_status]
    if wanted_risk:
        rows = [r for r in rows if r["risk"] == wanted_risk]
    rows.sort(key=lambda r: (RISK_ORDER.get(r["risk"], 3), r["re_kyc_due"] or "9999-12-31", r["code"]))
    return Response({"summary": counts, "results": rows})


# ---------- Audit log ----------

class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/audit/?action=&search=  (compliance officers and admins only)"""

    serializer_class = AuditEventSerializer

    def get_permissions(self):
        return [HasRole(), requires("view_audit")()]

    def get_queryset(self):
        qs = AuditEvent.objects.all()
        action_filter = self.request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(actor_name__icontains=search) | Q(target__icontains=search))
        return qs


# ---------- Overview dashboard ----------

@api_view(["GET"])
def overview(request):
    """Headline numbers for the Overview screen, in one request."""
    customers = Customer.objects.all()
    scores = [float(s) for s in customers.exclude(trust_score=None).values_list("trust_score", flat=True)]

    # Customers per 0.1 band of trust score: 0.0-0.1, ..., 0.9-1.0 (a score of exactly 1.0 goes in the last).
    histogram = [0] * 10
    for score in scores:
        histogram[min(int(score * 10), 9)] += 1

    lowest = customers_with_details().exclude(trust_score=None).order_by("trust_score", "id")[:5]

    return Response({
        "customers": customers.count(),
        "source_records": SourceRecord.objects.count(),
        "average_trust": f"{customers.aggregate(a=Avg('trust_score'))['a'] or 0:.3f}",
        "bands": {band: customers.filter(q).count() for band, q in BAND_FILTERS.items()},
        "histogram": [{"from": i / 10, "to": (i + 1) / 10, "count": n} for i, n in enumerate(histogram)],
        "pending_reviews": MatchSuggestion.objects.filter(status=MatchSuggestion.PENDING).count(),
        "pending_corrections": FieldCorrection.objects.filter(status=FieldCorrection.PENDING).count(),
        "last_synced_at": Source.objects.aggregate(m=Max("last_synced_at"))["m"],
        "sources": SourceSerializer(
            Source.objects.annotate(record_count=Count("records")).order_by("-trust", "name"), many=True
        ).data,
        "lowest_trust": CustomerListSerializer(lowest, many=True).data,
        **_quality_breakdown(),
    })


def _quality_breakdown():
    """Numbers for the Overview charts: every customer's score, where sources disagree, and how often each
    source agrees with the golden record (a trusted source that is often outvoted needs a closer look)."""
    from mdm.models import FIELDS
    from security.fields import compare_key

    golden = {}
    names = {}
    for g in GoldenField.objects.values("customer_id", "field", "value", "conflicts"):
        golden[(g["customer_id"], g["field"])] = (compare_key(g["field"], g["value"]), g["conflicts"])
        if g["field"] == "name":
            names[g["customer_id"]] = g["value"]

    scores = [
        {"id": c.id, "code": c.code, "name": names.get(c.id, ""), "score": str(c.trust_score)}
        for c in Customer.objects.exclude(trust_score=None).order_by("trust_score", "id")[:2000]
    ]

    conflicts = {f: 0 for f in FIELDS}
    for (_, field), (_, n) in golden.items():
        if n:
            conflicts[field] += 1

    agreement = {}
    records = SourceRecord.objects.filter(source__enabled=True).select_related("source", "customer_link")
    for r in records:
        link = getattr(r, "customer_link", None)
        if not link:
            continue
        row = agreement.setdefault(r.source_id, {"code": r.source.code, "name": r.source.name,
                                                 "trust": str(r.source.trust), "held": 0, "matched": 0})
        for f in FIELDS:
            value = getattr(r, f)
            if value in (None, ""):
                continue
            row["held"] += 1
            if golden.get((link.customer_id, f), (None,))[0] == compare_key(f, value):
                row["matched"] += 1

    return {
        "scores": scores,
        "conflicts_by_field": [{"field": f, "customers": conflicts[f]} for f in FIELDS],
        "source_agreement": sorted(agreement.values(), key=lambda x: x["matched"] / max(x["held"], 1)),
    }


# ---------- Reference (powers the "How Lumina works" page) ----------

@api_view(["GET"])
def reference(request):
    """The live rules of the system, read from the code and the database, so the help page never drifts."""
    from accounts import roles as r
    from mdm import matching
    from mdm.models import FieldWeight

    return Response({
        "roles": [
            {"role": role, "label": r.LABELS[role],
             "capabilities": sorted(c for c, members in r.CAPABILITIES.items() if role in members)}
            for role in [r.RELATIONSHIP_MANAGER, r.AGENT, r.STEWARD, r.COMPLIANCE, r.ADMIN]
        ],
        "weights": {f: str(w) for f, w in FieldWeight.objects.values_list("field", "weight")},
        "sources": [{"code": s.code, "name": s.name, "trust": str(s.trust), "enabled": s.enabled}
                    for s in Source.objects.order_by("-trust", "name")],
        "matching": {
            "points_pan": matching.POINTS_PAN,
            "points_mobile": matching.POINTS_MOBILE,
            "points_email": matching.POINTS_EMAIL,
            "points_dob": matching.POINTS_DOB,
            "points_name_max": matching.POINTS_NAME_MAX,
            "match_threshold": matching.MATCH_THRESHOLD,
            "review_threshold": matching.REVIEW_THRESHOLD,
            "min_name_similarity": matching.MIN_NAME_SIMILARITY,
        },
        "bands": {"medium": "0.6", "high": "0.8"},
        "correction_trust": str(FieldCorrection.TRUST),
    })
