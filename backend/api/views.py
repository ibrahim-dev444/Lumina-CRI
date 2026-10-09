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
        return [HasRole()]

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
    })


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
