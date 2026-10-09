"""Turn our models into the JSON the React app receives."""

from rest_framework import serializers

from accounts.masking import MASKERS, mask
from security.fields import compare_key, display
from accounts.roles import can
from compliance.models import PURPOSES, KycRecord
from compliance.services import current_consents, summary as kyc_summary
from audit.models import AuditEvent

from ingestion.models import SourceRecord
from mdm.models import FIELDS, Customer, FieldCorrection, FieldWeight, GoldenField, MatchSuggestion
from sources.models import Source

LOW_TRUST = 0.40  # a golden value at or below this trust needs a steward to look at it


def trust_band(score):
    if score is None:
        return "low"
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "medium"
    return "low"


class SourceSerializer(serializers.ModelSerializer):
    record_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Source
        fields = ["code", "name", "category", "trust", "enabled", "last_synced_at", "record_count"]
        read_only_fields = ["code", "name", "category", "last_synced_at"]


class CustomerListSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    name = serializers.SerializerMethodField()
    band = serializers.SerializerMethodField()
    record_count = serializers.SerializerMethodField()
    sources = serializers.SerializerMethodField()
    conflict_fields = serializers.SerializerMethodField()
    needs_review = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ["id", "code", "name", "trust_score", "band", "record_count", "sources", "conflict_fields",
                  "kyc_status",
                  "needs_review", "score_updated_at"]

    # These read from prefetched golden_fields and links (see CustomerViewSet), so no extra queries.
    def _golden(self, obj):
        return {g.field: g for g in obj.golden_fields.all()}

    def get_name(self, obj):
        g = self._golden(obj).get("name")
        return g.value if g else ""

    def get_kyc_status(self, obj):
        """'verified', 'due_soon', 'overdue' or 'no_record'. KYC rows are loaded once per request."""
        cache = self.context.setdefault("_kyc", {})
        if obj.pan_hash and obj.pan_hash not in cache:
            cache.update({k.pan_hash: k for k in KycRecord.objects.filter(pan_hash=obj.pan_hash)})
        return kyc_summary(cache.get(obj.pan_hash))["kyc_status"]

    def get_band(self, obj):
        return trust_band(obj.trust_score)

    def get_record_count(self, obj):
        return len(obj.links.all())

    def get_sources(self, obj):
        """Codes of the sources this customer was found in, most trusted first."""
        sources = {link.source_record.source for link in obj.links.all()}
        return [s.code for s in sorted(sources, key=lambda s: (-s.trust, s.code))]

    def get_conflict_fields(self, obj):
        return sum(1 for g in self._golden(obj).values() if g.conflicts)

    def get_needs_review(self, obj):
        """Fields that are missing, or whose best value comes from a low-trust source."""
        golden = self._golden(obj)
        return sum(1 for f in FIELDS if f not in golden or golden[f].trust <= LOW_TRUST)


def shows_pii(context):
    """True if the signed-in user may see full personal data. Needs the request in the serializer context."""
    request = context.get("request")
    return bool(request and can(request.user, "view_pii"))


class GoldenFieldSerializer(serializers.ModelSerializer):
    source_code = serializers.SerializerMethodField()
    source_name = serializers.SerializerMethodField()
    last_updated = serializers.SerializerMethodField()
    correction = serializers.SerializerMethodField()

    class Meta:
        model = GoldenField
        fields = ["field", "value", "trust", "conflicts", "source_code", "source_name", "source_record_id",
                  "last_updated", "correction"]

    # A golden value comes from a source record, or from an approved correction.
    def get_source_code(self, obj):
        return obj.source.code if obj.source_id else "correction"

    def get_source_name(self, obj):
        return obj.source.name if obj.source_id else "Approved correction"

    def get_last_updated(self, obj):
        when = obj.source_record.source_updated_at if obj.source_record_id else obj.correction.decided_at
        return serializers.DateTimeField().to_representation(when) if when else None

    def get_correction(self, obj):
        c = obj.correction
        if not c:
            return None
        return {"id": c.id, "evidence_ref": c.evidence_ref, "proposed_by": c.proposed_by_name,
                "approved_by": c.decided_by_name}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["value"] = display(instance.field, data["value"])
        if not shows_pii(self.context):
            data["value"] = mask(instance.field, data["value"])
        return data


class FieldCorrectionSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    mine = serializers.SerializerMethodField()

    class Meta:
        model = FieldCorrection
        fields = ["id", "customer", "field", "value", "previous_value", "evidence_ref", "reason", "status",
                  "proposed_by_name", "proposed_at", "decided_by_name", "decided_at", "decision_note", "mine"]

    def get_customer(self, obj):
        name = next((g.value for g in obj.customer.golden_fields.all() if g.field == "name"), "")
        return {"id": obj.customer_id, "code": obj.customer.code, "name": name}

    def get_mine(self, obj):
        """True when the signed-in user proposed it, so the screen can say they cannot approve it."""
        request = self.context.get("request")
        return bool(request and obj.proposed_by_id == request.user.id)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["value"] = display(instance.field, data["value"])
        if not shows_pii(self.context):
            data["value"] = mask(instance.field, data["value"])
            data["previous_value"] = mask(instance.field, data["previous_value"])
        return data


class SourceRecordSerializer(serializers.ModelSerializer):
    source_code = serializers.CharField(source="source.code")
    source_name = serializers.CharField(source="source.name")
    source_trust = serializers.DecimalField(source="source.trust", max_digits=3, decimal_places=2)
    source_enabled = serializers.BooleanField(source="source.enabled")
    match_reason = serializers.CharField(source="customer_link.match_reason", default="")

    class Meta:
        model = SourceRecord
        fields = ["id", "source_code", "source_name", "source_trust", "source_enabled", "source_record_id",
                  *FIELDS, "source_updated_at", "match_reason"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field in FIELDS:
            data[field] = display(field, data[field])  # PAN, CKYC, Aadhaar always masked
        if not shows_pii(self.context):
            for field in MASKERS:
                data[field] = mask(field, data[field])
        # Does each value agree with the golden record? Worked out here, on the server, because masked
        # or encrypted values cannot be compared in the browser.
        golden = self.context.get("golden_keys")
        if golden is not None:
            data["agreement"] = {
                f: None if not getattr(instance, f) else compare_key(f, getattr(instance, f)) == golden.get(f)
                for f in FIELDS
            }
        return data


class CustomerDetailSerializer(CustomerListSerializer):
    golden = serializers.SerializerMethodField()
    records = serializers.SerializerMethodField()
    weights = serializers.SerializerMethodField()
    masked = serializers.SerializerMethodField()
    corrections = serializers.SerializerMethodField()
    compliance = serializers.SerializerMethodField()

    class Meta(CustomerListSerializer.Meta):
        fields = CustomerListSerializer.Meta.fields + ["golden", "records", "weights", "masked", "corrections",
                                                       "compliance"]

    def get_compliance(self, obj):
        """KYC status and consent for everyone; AML risk, PEP and sanctions only for compliance roles."""
        kyc = KycRecord.objects.filter(pan_hash=obj.pan_hash).first() if obj.pan_hash else None
        current = current_consents(obj.pan_hash)
        data = {
            **kyc_summary(kyc),
            "has_pan": bool(obj.pan_hash),
            "consents": [
                {
                    "purpose": key,
                    "label": label,
                    "status": current[key].status if current[key] else "unknown",
                    "channel": current[key].channel if current[key] else "",
                    "recorded_by": current[key].recorded_by_name if current[key] else "",
                    "recorded_at": current[key].recorded_at.isoformat() if current[key] else None,
                }
                for key, label in PURPOSES
            ],
            "aml": None,
        }
        request = self.context.get("request")
        if kyc and request and can(request.user, "view_compliance"):
            data["aml"] = {
                "risk": kyc.risk,
                "risk_reason": kyc.risk_reason,
                "last_kyc": kyc.last_kyc.isoformat(),
                "pep": kyc.pep,
                "pep_note": kyc.pep_note,
                "sanctions": kyc.sanctions,
                "sanctions_checked": kyc.sanctions_checked.isoformat() if kyc.sanctions_checked else None,
            }
        return data

    def get_corrections(self, obj):
        """The 10 most recent corrections for this customer, any status."""
        latest = obj.corrections.select_related("customer").prefetch_related("customer__golden_fields")[:10]
        return FieldCorrectionSerializer(latest, many=True, context=self.context).data

    def get_masked(self, obj):
        """Tells the screen that mobile, email and date of birth were hidden for this user's role."""
        return not shows_pii(self.context)

    def get_weights(self, obj):
        """Field weights, so the screen can show how much each field adds to the score."""
        return {f: str(w) for f, w in FieldWeight.objects.values_list("field", "weight")}

    def get_golden(self, obj):
        order = {f: i for i, f in enumerate(FIELDS)}
        golden = sorted(obj.golden_fields.all(), key=lambda g: order[g.field])
        return GoldenFieldSerializer(golden, many=True, context=self.context).data

    def get_records(self, obj):
        records = sorted((link.source_record for link in obj.links.all()), key=lambda r: -r.source.trust)
        golden_keys = {g.field: compare_key(g.field, g.value) for g in obj.golden_fields.all()}
        return SourceRecordSerializer(records, many=True, context={**self.context, "golden_keys": golden_keys}).data


class MatchSuggestionSerializer(serializers.ModelSerializer):
    record_a = SourceRecordSerializer()
    record_b = SourceRecordSerializer()
    customer_a = serializers.SerializerMethodField()
    customer_b = serializers.SerializerMethodField()

    class Meta:
        model = MatchSuggestion
        fields = ["id", "points", "reason", "status", "created_at", "decided_at",
                  "record_a", "record_b", "customer_a", "customer_b"]

    def _customer(self, record):
        link = getattr(record, "customer_link", None)
        return {"id": link.customer_id, "code": link.customer.code} if link else None

    def get_customer_a(self, obj):
        return self._customer(obj.record_a)

    def get_customer_b(self, obj):
        return self._customer(obj.record_b)


class AuditEventSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display")

    class Meta:
        model = AuditEvent
        fields = ["id", "at", "actor_name", "role", "action", "action_label", "target", "detail", "ip"]
