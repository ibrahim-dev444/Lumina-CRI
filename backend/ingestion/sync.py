from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from security import crypto
from security.fields import ENCRYPTED_FIELDS
from sources.models import Source

from .clean import clean_aadhaar, clean_record
from .connectors import CONNECTORS
from .models import RawRecord, SourceRecord


@dataclass
class SyncResult:
    fetched: int = 0
    created: int = 0
    updated: int = 0


def _aware(dt):
    """Source systems often store times without a time zone; treat them as Indian time."""
    if dt and timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def _protect_raw(raw, sensitive_columns):
    """The raw copy is kept as proof, but never with readable identity numbers."""
    safe = dict(raw)
    for column, field in sensitive_columns.items():
        value = safe.get(column)
        if value in (None, ""):
            continue
        if field == "aadhaar":
            last4 = clean_aadhaar(value)
            safe[column] = f"XXXX XXXX {last4}" if last4 else ""
        else:
            safe[column] = crypto.encrypt(str(value))
    return safe


def _protect_record(std):
    """Encrypt PAN and CKYC, and add their fingerprints for matching."""
    for field in ENCRYPTED_FIELDS:
        plain = std.get(field) or ""
        std[f"{field}_hash"] = crypto.fingerprint(plain)
        std[field] = crypto.encrypt(plain)
    return std


def sync_source(source_code):
    """Pull every customer from one source, keep the raw copy, and save the cleaned version."""
    source = Source.objects.get(code=source_code)
    if not source.enabled:
        raise ValueError(f"Source '{source_code}' is disabled.")
    if source_code not in CONNECTORS:
        raise ValueError(f"No connector written yet for '{source_code}'.")

    connector = CONNECTORS[source_code]()
    rows = connector.fetch()  # read the external system before opening our transaction

    result = SyncResult(fetched=len(rows))
    # All rows are saved together or not at all, so a failure halfway leaves no half-synced data.
    with transaction.atomic():
        for raw in rows:
            record_id = connector.record_id(raw)
            RawRecord.objects.create(
                source=source, source_record_id=record_id, payload=_protect_raw(raw, connector.sensitive_columns)
            )

            std = _protect_record(clean_record(connector.to_standard(raw)))
            std["source_updated_at"] = _aware(std.get("source_updated_at"))
            _, created = SourceRecord.objects.update_or_create(
                source=source, source_record_id=record_id, defaults=std
            )
            if created:
                result.created += 1
            else:
                result.updated += 1

        source.last_synced_at = timezone.now()
        source.save(update_fields=["last_synced_at"])
    return result
