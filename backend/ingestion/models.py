from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from sources.models import Source


class RawRecord(models.Model):
    """One row exactly as a source system sent it. Never edited; kept as proof of where data came from."""

    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="raw_records")
    source_record_id = models.CharField(max_length=64)  # the customer's ID inside that system, e.g. "FX0000101"
    payload = models.JSONField(encoder=DjangoJSONEncoder)  # DjangoJSONEncoder lets dates be stored as JSON
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fetched_at"]
        indexes = [models.Index(fields=["source", "source_record_id"])]

    def __str__(self):
        return f"{self.source.code}:{self.source_record_id} @ {self.fetched_at:%Y-%m-%d %H:%M}"


class SourceRecord(models.Model):
    """The latest cleaned version of one customer from one source, in Lumina's standard fields."""

    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="records")
    source_record_id = models.CharField(max_length=64)
    name = models.CharField(max_length=200, blank=True)
    father_name = models.CharField(max_length=200, blank=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    # PAN and CKYC are encrypted (security/crypto.py). The *_hash columns hold a keyed fingerprint so
    # records can be matched without decrypting. Aadhaar: last 4 digits only, never the full number.
    pan = models.TextField(blank=True)
    pan_hash = models.CharField(max_length=64, blank=True, db_index=True)
    aadhaar = models.CharField(max_length=4, blank=True)
    ckyc = models.TextField(blank=True)
    ckyc_hash = models.CharField(max_length=64, blank=True, db_index=True)
    mobile = models.CharField(max_length=10, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=300, blank=True)  # current address
    perm_address = models.CharField(max_length=300, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    income = models.CharField(max_length=60, blank=True)  # an income band, e.g. "10 to 25 lakh"
    source_updated_at = models.DateTimeField(null=True, blank=True)  # when the source system last changed this row
    synced_at = models.DateTimeField(auto_now=True)  # when Lumina last read it

    class Meta:
        ordering = ["source", "source_record_id"]
        constraints = [
            models.UniqueConstraint(fields=["source", "source_record_id"], name="unique_record_per_source"),
        ]

    def __str__(self):
        return f"{self.source.code}:{self.source_record_id} {self.name}"
