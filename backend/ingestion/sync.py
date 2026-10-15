from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from security import crypto
from security.fields import ENCRYPTED_FIELDS
from sources.models import Source, SyncRun

from .clean import clean_aadhaar, clean_record
from .connectors import CONNECTORS
from .connectors.adapters import FILE_KEY
from .connectors.catalog import DEMO_TYPES
from .connectors.generic import MappedConnector
from .models import RawRecord, SourceRecord


@dataclass
class SyncResult:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    accounts: int | None = None  # products read, when the source has an accounts mapping


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


def connector_for(source):
    """The built-in demo sources use their hand-written connectors; everything else reads its mapping."""
    if source.connector_type in DEMO_TYPES or not source.connector_type:
        if source.code not in CONNECTORS:
            raise ValueError(f"No connector written yet for '{source.code}'.")
        return CONNECTORS[source.code]()
    return MappedConnector(source)


def sync_source(source_code, started_by=""):
    """Pull every customer from one source, keep the raw copy, and save the cleaned version.
    Every attempt, good or failed, is written to the source's sync history."""
    source = Source.objects.get(code=source_code)
    if not source.enabled:
        raise ValueError(f"Source '{source_code}' is disabled.")
    try:
        result = _sync(source)
    except Exception as exc:
        SyncRun.objects.create(
            source=source, status=SyncRun.FAILED, error=str(exc)[:500], started_by=started_by,
            finished_at=timezone.now(),
        )
        raise
    SyncRun.objects.create(
        source=source, status=SyncRun.OK, fetched=result.fetched, created=result.created, updated=result.updated,
        started_by=started_by, finished_at=timezone.now(),
    )
    return result


def _sync(source):
    connector = connector_for(source)
    rows = connector.fetch()  # read the external system before opening our transaction
    accounts = connector.fetch_accounts() if hasattr(connector, "fetch_accounts") else None
    with transaction.atomic():  # customers and their products are saved together or not at all
        result = _store(source, connector, rows)
        if accounts is not None:
            from products.services import store_accounts

            result.accounts = store_accounts(source, accounts, source.mapping["accounts"])
    return result


def ingest_records(source, rows, started_by):
    """Store records a bank's own system sent to the push API. Same raw copy, cleaning, encryption and
    sync history as a pull; rows have Lumina's own field names plus "id" and optional "updated_at"."""
    from .connectors.push import PushConnector

    try:
        result = _store(source, PushConnector(), rows)
    except Exception as exc:
        SyncRun.objects.create(source=source, status=SyncRun.FAILED, error=str(exc)[:500], started_by=started_by,
                               finished_at=timezone.now())
        raise
    SyncRun.objects.create(source=source, status=SyncRun.OK, fetched=result.fetched, created=result.created,
                           updated=result.updated, started_by=started_by, finished_at=timezone.now())
    return result


def _store(source, connector, rows):

    result = SyncResult(fetched=len(rows))
    # All rows are saved together or not at all, so a failure halfway leaves no half-synced data.
    with transaction.atomic():
        seen = set()
        for raw in rows:
            raw = dict(raw)
            origin_file = raw.pop(FILE_KEY, None)  # which uploaded file the row came from (file uploads only)
            record_id = connector.record_id(raw)
            if not record_id:
                continue  # a row without an ID cannot be followed over time; skip it
            seen.add(record_id)
            RawRecord.objects.create(
                source=source, source_record_id=record_id, payload=_protect_raw(raw, connector.sensitive_columns)
            )

            std = _protect_record(clean_record(connector.to_standard(raw)))
            std["source_updated_at"] = _aware(std.get("source_updated_at"))
            std["active"] = True
            if origin_file is not None:
                std["origin_file_id"] = origin_file
            _, created = SourceRecord.objects.update_or_create(
                source=source, source_record_id=record_id, defaults=std
            )
            if created:
                result.created += 1
            else:
                result.updated += 1

        if source.connector_type == "file_upload":
            # Rows only suspended files hold are kept but switched off, so resuming brings back the same customer.
            SourceRecord.objects.filter(source=source).exclude(source_record_id__in=seen).update(active=False)
        source.last_synced_at = timezone.now()
        source.save(update_fields=["last_synced_at"])
    return result
