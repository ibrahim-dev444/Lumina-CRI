"""Compliance lookups and changes. The API and commands call these."""

import csv
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction

from ingestion.clean import clean_date, clean_pan
from security.crypto import fingerprint

from .models import PURPOSES, ConsentRecord, KycRecord

PURPOSE_KEYS = [p for p, _ in PURPOSES]
FEED_FILE = Path(settings.BASE_DIR).parent / "fake_sources" / "compliance" / "kyc_aml.csv"


class ConsentError(ValueError):
    pass


def kyc_for(pan_hash):
    return KycRecord.objects.filter(pan_hash=pan_hash).first() if pan_hash else None


def current_consents(pan_hash):
    """{purpose: newest ConsentRecord or None} for every purpose."""
    current = {p: None for p in PURPOSE_KEYS}
    if pan_hash:
        for c in ConsentRecord.objects.filter(pan_hash=pan_hash).order_by("recorded_at", "id"):
            current[c.purpose] = c
    return current


@transaction.atomic
def record_consent(pan_hash, purpose, status, channel, note, user_name):
    if not pan_hash:
        raise ConsentError("This customer has no PAN on file, so consent cannot be linked to them yet.")
    if purpose not in PURPOSE_KEYS:
        raise ConsentError("Unknown purpose.")
    if status not in dict(ConsentRecord.STATUS_CHOICES):
        raise ConsentError("Status must be granted, revoked or pending.")
    channel = (channel or "").strip()
    if not channel:
        raise ConsentError("Say how the customer told us (call, branch, email ...).")
    if purpose == "servicing" and status == ConsentRecord.REVOKED:
        raise ConsentError("Servicing consent cannot be revoked while the customer holds an account.")
    current = current_consents(pan_hash)[purpose]
    if current and current.status == status:
        raise ConsentError(f"Consent for this purpose is already {status}.")
    return ConsentRecord.objects.create(
        pan_hash=pan_hash, purpose=purpose, status=status, channel=channel,
        note=(note or "").strip(), recorded_by_name=user_name,
    )


def _parse_date(value):
    d = clean_date(value)
    if isinstance(d, datetime):
        return d.date()
    return d


@transaction.atomic
def import_feed(path=FEED_FILE):
    """Load the (fake) compliance feed: KYC/AML status and consent, one row per PAN.
    Returns (kyc_rows, consent_changes). Re-running is safe: unchanged consent is not duplicated."""
    kyc_rows = consent_changes = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pan = clean_pan(row.get("PAN"))
            if not pan:
                continue
            key = fingerprint(pan)
            last_kyc = _parse_date(row.get("Last KYC"))
            if not last_kyc:
                continue
            KycRecord.objects.update_or_create(pan_hash=key, defaults={
                "risk": row["AML Risk"].strip().lower(),
                "risk_reason": row.get("Risk Reason", "").strip(),
                "last_kyc": last_kyc,
                "pep": row.get("PEP", "").strip().lower() in ("yes", "y", "true"),
                "pep_note": row.get("PEP Note", "").strip(),
                "sanctions": "potential_match" if row.get("Sanctions", "").strip().lower().startswith("potential")
                else "clear",
                "sanctions_checked": _parse_date(row.get("Sanctions Checked")),
            })
            kyc_rows += 1
            current = current_consents(key)
            for purpose, label in PURPOSES:
                status = (row.get(f"Consent {label}") or "").strip().lower()
                if status not in dict(ConsentRecord.STATUS_CHOICES):
                    continue
                if current[purpose] and current[purpose].status == status:
                    continue
                ConsentRecord.objects.create(pan_hash=key, purpose=purpose, status=status,
                                             channel="Bank records import", recorded_by_name="system")
                consent_changes += 1
    return kyc_rows, consent_changes


def summary(kyc, today=None):
    """Compliance facts for one customer, as plain data for the API."""
    if not kyc:
        return {"kyc_status": "no_record", "re_kyc_due": None}
    return {"kyc_status": kyc.status(today), "re_kyc_due": kyc.re_kyc_due.isoformat()}


def today():
    return date.today()
