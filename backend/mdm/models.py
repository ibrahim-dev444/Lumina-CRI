from decimal import Decimal

from django.conf import settings
from django.db import models

from ingestion.models import SourceRecord
from sources.models import Source

# The fields that make up a golden record, in display order.
FIELDS = ["name", "mobile", "email", "address", "dob"]
FIELD_CHOICES = [(f, f) for f in FIELDS]


class Customer(models.Model):
    """One real person, after matching. Built from one or more SourceRecords."""

    created_at = models.DateTimeField(auto_now_add=True)
    trust_score = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)  # 0.000 to 1.000
    score_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def code(self):
        """Human-friendly ID shown on screens, e.g. C-10001."""
        return f"C-{10000 + self.id}"

    def __str__(self):
        return self.code


class CustomerLink(models.Model):
    """Says: this source record belongs to this customer, and why we think so.

    Kept in mdm (not as a column on SourceRecord) so each module only writes its own tables.
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="links")
    source_record = models.OneToOneField(SourceRecord, on_delete=models.CASCADE, related_name="customer_link")
    match_reason = models.CharField(max_length=200)  # e.g. "same mobile + dob, name 72%" or "only record"
    linked_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.source_record} -> {self.customer}"


class FieldCorrection(models.Model):
    """A person's fix to one field of one customer, backed by evidence.

    Maker-checker: one person proposes, a different person approves or rejects. Only approved
    corrections feed the golden record, where they win over every source (trust 1.00).
    The rules for who may do what live in stewardship/services.py.
    """

    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]
    TRUST = Decimal("1.00")  # an approved correction outranks every source

    # PROTECT: a customer with corrections is never deleted by accident; merges move them instead.
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="corrections")
    field = models.CharField(max_length=20, choices=FIELD_CHOICES)
    value = models.TextField()
    previous_value = models.TextField(blank=True)  # the golden value when the fix was proposed
    evidence_ref = models.CharField(max_length=120)  # e.g. "KYC form #4471" or "call recording 2026-10-09"
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True)

    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    proposed_by_name = models.CharField(max_length=150)
    proposed_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_by_name = models.CharField(max_length=150, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-proposed_at", "-id"]

    def __str__(self):
        return f"{self.customer} {self.field} -> {self.value} ({self.status})"


class GoldenField(models.Model):
    """The value Lumina believes for one field of one customer, and where it came from.

    It comes either from a source record, or from an approved correction (then source and
    source_record are empty).
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="golden_fields")
    field = models.CharField(max_length=20, choices=FIELD_CHOICES)
    value = models.TextField()
    source = models.ForeignKey(Source, on_delete=models.PROTECT, null=True, blank=True)
    source_record = models.ForeignKey(SourceRecord, on_delete=models.CASCADE, null=True, blank=True)
    correction = models.ForeignKey(FieldCorrection, on_delete=models.CASCADE, null=True, blank=True)
    trust = models.DecimalField(max_digits=3, decimal_places=2)
    conflicts = models.PositiveSmallIntegerField(default=0)  # how many OTHER different values sources hold

    class Meta:
        ordering = ["customer", "field"]
        constraints = [models.UniqueConstraint(fields=["customer", "field"], name="one_golden_value_per_field")]

    def __str__(self):
        return f"{self.customer} {self.field}={self.value}"


class MatchSuggestion(models.Model):
    """Two records that are probably the same person, but not sure enough to merge automatically.

    A data steward accepts or rejects it. Accepted pairs are merged on the next matching run.
    """

    PENDING, ACCEPTED, REJECTED = "pending", "accepted", "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (ACCEPTED, "Accepted"), (REJECTED, "Rejected")]

    record_a = models.ForeignKey(SourceRecord, on_delete=models.CASCADE, related_name="+")
    record_b = models.ForeignKey(SourceRecord, on_delete=models.CASCADE, related_name="+")
    points = models.PositiveSmallIntegerField()
    reason = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-points"]
        constraints = [models.UniqueConstraint(fields=["record_a", "record_b"], name="one_suggestion_per_pair")]

    def __str__(self):
        return f"{self.record_a} ~ {self.record_b} ({self.points} pts, {self.status})"


class FieldWeight(models.Model):
    """How much each field counts in the trust score. All weights together should add up to 1.00."""

    field = models.CharField(max_length=20, choices=FIELD_CHOICES, unique=True)
    weight = models.DecimalField(max_digits=3, decimal_places=2)

    def __str__(self):
        return f"{self.field}: {self.weight}"
