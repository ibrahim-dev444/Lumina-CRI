"""Corrections workflow: propose a fix with evidence, then a different person approves or rejects it.

This is the "maker-checker" rule banks use for changes to customer data: no single person can both
make a change and sign it off.
"""

from django.db import transaction
from django.utils import timezone

from ingestion.clean import (
    clean_address,
    clean_ckyc,
    clean_date,
    clean_email,
    clean_gender,
    clean_mobile,
    clean_name,
    clean_pan,
    clean_text,
)
from mdm.models import FIELDS, FieldCorrection, GoldenField
from mdm.services import rebuild_golden_record
from security.fields import compare_key, display, protect


class CorrectionError(ValueError):
    """A rule was broken; the message is shown to the user as it is."""


def _clean_value(field, raw):
    """Apply the same cleaning as the connectors, so a correction looks like any other value."""
    raw = (raw or "").strip()
    if field == "mobile":
        value = clean_mobile(raw)
        if not value:
            raise CorrectionError("Enter a 10-digit Indian mobile number, e.g. 9822104521.")
        return value
    if field == "email":
        value = clean_email(raw)
        if not value:
            raise CorrectionError("Enter a full email address, e.g. name@example.com.")
        return value
    if field == "dob":
        value = clean_date(raw)
        if not value:
            raise CorrectionError("Enter the date of birth as YYYY-MM-DD or DD/MM/YYYY.")
        return value.isoformat()
    if field == "aadhaar":
        raise CorrectionError("Aadhaar cannot be corrected here: Lumina only keeps its last 4 digits.")
    if field == "pan":
        value = clean_pan(raw)
        if not value:
            raise CorrectionError("Enter the PAN as 5 letters, 4 digits and 1 letter, e.g. ABCPK1234F.")
        return value
    if field == "ckyc":
        value = clean_ckyc(raw)
        if not value:
            raise CorrectionError("Enter the CKYC number as 14 digits.")
        return value
    if field == "gender":
        value = clean_gender(raw)
        if not value:
            raise CorrectionError("Enter Male, Female or Other.")
        return value
    if field in ("name", "father_name"):
        value = clean_name(raw)
    elif field in ("address", "perm_address"):
        value = clean_address(raw)
    else:
        value = clean_text(raw)
    if not value:
        raise CorrectionError("Enter the correct value.")
    return value


@transaction.atomic
def propose(customer, field, value, evidence_ref, reason, user):
    if field not in FIELDS:
        raise CorrectionError("Unknown field.")
    evidence_ref = (evidence_ref or "").strip()
    reason = (reason or "").strip()
    if not evidence_ref:
        raise CorrectionError("Give an evidence reference, e.g. a KYC form number or call ID.")
    if not reason:
        raise CorrectionError("Explain why the current value is wrong.")
    if customer.corrections.filter(field=field, status=FieldCorrection.PENDING).exists():
        raise CorrectionError("A correction for this field is already waiting for approval.")

    cleaned = protect(field, _clean_value(field, value))  # PAN and CKYC are stored encrypted
    current = GoldenField.objects.filter(customer=customer, field=field).values_list("value", flat=True).first()
    if current and compare_key(field, current) == compare_key(field, cleaned):
        raise CorrectionError("That is already the value in the golden record.")

    return FieldCorrection.objects.create(
        customer=customer,
        field=field,
        value=cleaned,
        previous_value=display(field, current) or "",  # identity numbers kept masked
        evidence_ref=evidence_ref,
        reason=reason,
        proposed_by=user,
        proposed_by_name=user.get_username(),
    )


@transaction.atomic
def decide(correction, approve, user, note=""):
    correction = FieldCorrection.objects.select_for_update().get(pk=correction.pk)
    if correction.status != FieldCorrection.PENDING:
        raise CorrectionError(f"This correction was already {correction.status}.")
    if correction.proposed_by_id == user.id:
        raise CorrectionError("You cannot approve or reject your own correction. Another person must check it.")
    note = (note or "").strip()
    if not approve and not note:
        raise CorrectionError("Say why you are rejecting it, so the proposer can fix it.")

    correction.status = FieldCorrection.APPROVED if approve else FieldCorrection.REJECTED
    correction.decided_by = user
    correction.decided_by_name = user.get_username()
    correction.decided_at = timezone.now()
    correction.decision_note = note
    correction.save()

    if approve:
        rebuild_golden_record(correction.customer)
    return correction
