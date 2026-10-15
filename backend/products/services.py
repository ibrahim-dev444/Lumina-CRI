"""Turning a source's account rows into Holdings, and reading a customer's products."""

import re
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from ingestion.clean import clean_date
from security import crypto

from .models import (ACTIVE, CLOSED, CREDIT_CARD, CURRENT, DEPOSIT, DEPOSITS, DORMANT, HOME_LOAN, LOANS, OTHER,
                     OTHER_LOAN, OVERDUE, PERSONAL_LOAN, SAVINGS, VEHICLE_LOAN, Holding)

# Lumina's account fields, which a source's columns are mapped to (besides the account and customer IDs).
ACCOUNT_FIELDS = ["product_type", "product_name", "status", "opened_on", "balance"]

# Words and short codes banks use, checked in order: the first hit decides.
_TYPE_WORDS = [
    (CREDIT_CARD, ["credit card", "card", "cc"]),
    (HOME_LOAN, ["home", "housing", "mortgage", "hl"]),
    (VEHICLE_LOAN, ["car", "auto", "vehicle", "two wheeler", "vl"]),
    (PERSONAL_LOAN, ["personal", "pl"]),
    (OTHER_LOAN, ["loan", "od", "overdraft", "lap", "gold"]),
    (DEPOSIT, ["fixed", "term deposit", "recurring", "deposit", "fd", "rd", "td"]),
    (CURRENT, ["current", "ca"]),
    (SAVINGS, ["saving", "savings", "sb", "sa", "salary"]),
]
_STATUS_WORDS = [
    (CLOSED, ["closed", "close", "c", "settled", "written off"]),
    (OVERDUE, ["overdue", "npa", "dpd", "delinquent", "default", "o", "arrears"]),
    (DORMANT, ["dormant", "inactive", "inoperative", "d", "frozen"]),
    (ACTIVE, ["active", "open", "regular", "live", "a", "standard"]),
]


def _words(text):
    return " " + " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower())) + " "


def _first(text, table):
    words = _words(text)
    for value, keys in table:
        if any(f" {k} " in words for k in keys):
            return value
    return None


def classify_type(*texts):
    """'SB' -> savings, 'Home Loan' -> home_loan. Tries the type column first, then the product name."""
    for text in texts:
        found = _first(text, _TYPE_WORDS)
        if found:
            return found
    return OTHER


def classify_status(text):
    """'NPA' -> overdue, 'Regular' -> active. Empty means active."""
    return _first(text, _STATUS_WORDS) or ACTIVE


def clean_amount(value):
    """'Rs 12,45,000.50' or 1245000.5 -> Decimal('1245000.50'). Anything unreadable -> None."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    text = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return Decimal(text).quantize(Decimal("0.01")) if text not in ("", "-", ".") else None
    except InvalidOperation:
        return None


@transaction.atomic
def store_accounts(source, rows, mapping):
    """Save one sync's account rows for a source. Accounts the source no longer lists are removed: the
    source is the truth for its own products. Returns how many accounts were stored."""
    from ingestion.connectors.generic import _when
    from ingestion.sync import _aware

    fields = mapping.get("fields") or {}
    updated_column = mapping.get("updated_column") or ""
    seen = []
    for raw in rows:
        account = str(raw.get(mapping["id_column"]) or "").strip()
        customer_ref = str(raw.get(mapping["customer_column"]) or "").strip()
        if not account or not customer_ref:
            continue
        value = {f: raw.get(column) for f, column in fields.items()}
        key = crypto.fingerprint(account)
        Holding.objects.update_or_create(
            source=source, account_key=key,
            defaults={
                "account_last4": re.sub(r"[^0-9A-Za-z]", "", account)[-4:],
                "customer_ref": customer_ref,
                "product_type": classify_type(value.get("product_type"), value.get("product_name")),
                "product_name": str(value.get("product_name") or "").strip()[:120],
                "status": classify_status(value.get("status")),
                "opened_on": clean_date(value.get("opened_on")),
                "balance": clean_amount(value.get("balance")),
                "source_updated_at": _aware(_when(raw.get(updated_column))) if updated_column else None,
            },
        )
        seen.append(key)
    Holding.objects.filter(source=source).exclude(account_key__in=seen).delete()
    return len(seen)


def holdings_for(customer):
    """Every product the customer's records point to, from sources that are switched on."""
    match = Q()
    for link in customer.links.select_related("source_record__source"):
        record = link.source_record
        if record.source.enabled and record.active:
            match |= Q(source_id=record.source_id, customer_ref=record.source_record_id)
    if not match:
        return Holding.objects.none()
    return Holding.objects.filter(match).select_related("source")


def summary(holdings):
    """Totals for the customer header: what they keep with the bank and what they owe. Closed products left out."""
    live = [h for h in holdings if h.status != CLOSED]
    deposits = sum((h.balance or 0 for h in live if h.product_type in DEPOSITS), Decimal("0"))
    owed = sum((h.balance or 0 for h in live if h.product_type in LOANS or h.product_type == CREDIT_CARD),
               Decimal("0"))
    return {
        "count": len(live),
        "deposits": deposits,
        "owed": owed,
        "overdue": sum(1 for h in live if h.status == OVERDUE),
        "dormant": sum(1 for h in live if h.status == DORMANT),
    }
