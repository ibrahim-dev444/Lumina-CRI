"""KYC, AML and consent.

These come from the bank's compliance systems, which identify a person by PAN. So each row is keyed by
the PAN fingerprint (security/crypto.py), not by Lumina's customer ID: when customers are merged or
re-matched, their compliance data still finds them, and no PAN is stored here in readable form.
"""

from datetime import date, timedelta

from django.db import models

# RBI periodic updation of KYC: high risk every 2 years, medium every 8, low every 10.
RE_KYC_YEARS = {"high": 2, "medium": 8, "low": 10}
DUE_SOON_DAYS = 180


def add_years(d, years):
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


class KycRecord(models.Model):
    LOW, MEDIUM, HIGH = "low", "medium", "high"
    RISK_CHOICES = [(LOW, "Low"), (MEDIUM, "Medium"), (HIGH, "High")]
    CLEAR, POTENTIAL_MATCH = "clear", "potential_match"
    SANCTIONS_CHOICES = [(CLEAR, "Clear"), (POTENTIAL_MATCH, "Potential match")]

    pan_hash = models.CharField(max_length=64, unique=True)
    risk = models.CharField(max_length=10, choices=RISK_CHOICES)
    risk_reason = models.CharField(max_length=200, blank=True)
    last_kyc = models.DateField()
    pep = models.BooleanField(default=False)  # politically exposed person, or closely linked to one
    pep_note = models.CharField(max_length=200, blank=True)
    sanctions = models.CharField(max_length=20, choices=SANCTIONS_CHOICES, default=CLEAR)
    sanctions_checked = models.DateField(null=True, blank=True)
    imported_at = models.DateTimeField(auto_now=True)

    @property
    def re_kyc_due(self):
        return add_years(self.last_kyc, RE_KYC_YEARS[self.risk])

    def status(self, today=None):
        """'overdue', 'due_soon' or 'verified'."""
        today = today or date.today()
        due = self.re_kyc_due
        if due < today:
            return "overdue"
        if due - today <= timedelta(days=DUE_SOON_DAYS):
            return "due_soon"
        return "verified"

    def __str__(self):
        return f"KYC {self.pan_hash[:8]} {self.risk}"


PURPOSES = [
    ("servicing", "Servicing"),
    ("marketing", "Marketing"),
    ("analytics", "Analytics"),
    ("cross_sell", "Cross-sell"),
    ("account_aggregator", "Account Aggregator"),
]


class ConsentRecord(models.Model):
    """One consent decision for one purpose. Append-only: the newest row per purpose is the current
    status, and older rows are the history the bank must be able to show."""

    GRANTED, REVOKED, PENDING = "granted", "revoked", "pending"
    STATUS_CHOICES = [(GRANTED, "Granted"), (REVOKED, "Revoked"), (PENDING, "Pending")]

    pan_hash = models.CharField(max_length=64, db_index=True)
    purpose = models.CharField(max_length=30, choices=PURPOSES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    channel = models.CharField(max_length=40)  # e.g. "Bank records import", "Call", "Branch"
    note = models.CharField(max_length=300, blank=True)
    recorded_by_name = models.CharField(max_length=150)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at", "-id"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Consent records cannot be changed; add a new one.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.purpose} {self.status}"
