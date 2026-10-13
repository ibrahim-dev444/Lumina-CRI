"""Accounts, deposits, loans and cards a customer holds, as the bank's systems report them.

Each row comes from one source and points at the customer's ID inside that source (customer_ref), the same ID
the source's customer rows use. So a product follows its customer through matching and merges without being
re-linked. The full account number is never stored: only a keyed fingerprint (to recognise the account on the
next sync) and its last four characters (to show it).
"""

from django.db import models

from sources.models import Source

SAVINGS, CURRENT, DEPOSIT = "savings", "current", "deposit"
HOME_LOAN, PERSONAL_LOAN, VEHICLE_LOAN, OTHER_LOAN = "home_loan", "personal_loan", "vehicle_loan", "loan"
CREDIT_CARD, OTHER = "credit_card", "other"
PRODUCT_TYPES = [
    (SAVINGS, "Savings account"),
    (CURRENT, "Current account"),
    (DEPOSIT, "Fixed or recurring deposit"),
    (HOME_LOAN, "Home loan"),
    (PERSONAL_LOAN, "Personal loan"),
    (VEHICLE_LOAN, "Vehicle loan"),
    (OTHER_LOAN, "Loan"),
    (CREDIT_CARD, "Credit card"),
    (OTHER, "Other product"),
]
DEPOSITS = {SAVINGS, CURRENT, DEPOSIT}
LOANS = {HOME_LOAN, PERSONAL_LOAN, VEHICLE_LOAN, OTHER_LOAN}

ACTIVE, OVERDUE, DORMANT, CLOSED = "active", "overdue", "dormant", "closed"
STATUSES = [(ACTIVE, "Active"), (OVERDUE, "Overdue"), (DORMANT, "Dormant"), (CLOSED, "Closed")]


class Holding(models.Model):
    """One product one customer holds in one source system."""

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="holdings")
    account_key = models.CharField(max_length=64)  # keyed fingerprint of the account number in that system
    account_last4 = models.CharField(max_length=4, blank=True)
    customer_ref = models.CharField(max_length=64, db_index=True)  # the customer's record ID in the same source
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES)
    product_name = models.CharField(max_length=120, blank=True)  # the bank's own name, e.g. "Priority Savings"
    status = models.CharField(max_length=10, choices=STATUSES, default=ACTIVE)
    opened_on = models.DateField(null=True, blank=True)
    # Deposits: the balance. Loans and cards: what is owed. Rupees.
    balance = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product_type", "opened_on", "id"]
        constraints = [models.UniqueConstraint(fields=["source", "account_key"], name="one_holding_per_account")]

    def __str__(self):
        return f"{self.get_product_type_display()} XX{self.account_last4} ({self.source.code})"
