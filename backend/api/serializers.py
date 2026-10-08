"""Turn our models into the JSON the React app receives."""

from rest_framework import serializers

from accounts.masking import MASKERS, mask
from accounts.roles import can
from audit.models import AuditEvent

from ingestion.models import SourceRecord
from mdm.models import FIELDS, Customer, FieldWeight, GoldenField, MatchSuggestion
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

    class Meta:
        model = Customer
        fields = ["id", "code", "name", "trust_score", "band", "record_count", "sources", "conflict_fields",
                  "needs_review", "score_updated_at"]

    # These read from prefetched golden_fields and links (see CustomerViewSet), so no extra queries.
    def _golden(self, obj):
        return {g.field: g for g in obj.golden_fields.all()}

    def get_name(self, obj):
        g = self._golden(obj).get("name")
        return g.value if g else ""

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
    source_code = serializers.CharField(source="source.code")
    source_name = serializers.CharField(source="source.name")
    last_updated = serializers.DateTimeField(source="source_record.source_updated_at")

    class Meta:
        model = GoldenField
        fields = ["field", "value", "trust", "conflicts", "source_code", "source_name", "source_record_id",
                  "last_updated"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not shows_pii(self.context):
            data["value"] = mask(instance.field, data["value"])
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
                  "name", "mobile", "email", "address", "dob", "source_updated_at", "match_reason"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not shows_pii(self.context):
            for field in MASKERS:
                data[field] = mask(field, data[field])
        return data


class CustomerDetailSerializer(CustomerListSerializer):
    golden = serializers.SerializerMethodField()
    records = serializers.SerializerMethodField()
    weights = serializers.SerializerMethodField()
    masked = serializers.SerializerMethodField()

    class Meta(CustomerListSerializer.Meta):
        fields = CustomerListSerializer.Meta.fields + ["golden", "records", "weights", "masked"]

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
        return SourceRecordSerializer(records, many=True, context=self.context).data


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
