"""Many CSV files on one file-upload connector: upload several at once, suspend or resume them, remove them.

A sync reads every active file (the newest file wins when the same customer ID is in several). Suspending
switches off the rows only suspended files hold, without deleting them, so resuming brings back the same
customers with the same IDs. Removing deletes the files, and the rows and customers only they held.
"""

import re
from dataclasses import dataclass

from django.db import transaction

from sources.models import UploadedFile

from .connectors.adapters import ConnectorError, csv_header, parse_csv_upload

MAX_FILES = 20  # per upload
MAX_BYTES = 5 * 1024 * 1024  # per file (parse_csv_upload checks it)


LUMINA_ID = re.compile(r"^C-\d{5,}$")  # Lumina's own customer IDs, e.g. C-10168


def upload_files(source, uploads, username):
    """Check and save each file. Returns one result per file: {name, ok, rows | error}, and for saved files what
    to look at: mapped columns it lacks (missing), columns no earlier file had (new_columns), and whether its IDs
    look like Lumina's own customer IDs (lumina_ids). Files may differ in columns; good files are kept even when
    others in the same batch are refused."""
    if not uploads:
        raise ConnectorError("Choose one or more CSV files.")
    if len(uploads) > MAX_FILES:
        raise ConnectorError(f"Upload at most {MAX_FILES} files at a time.")
    mapping = source.mapping or {}
    needed = [c for c in [mapping.get("id_column"), mapping.get("updated_column"), mapping.get("product_column"),
                          *(mapping.get("fields") or {}).values()] if c]
    known = {c for f in source.uploads.filter(status=UploadedFile.ACTIVE) for c in csv_header(f.content)}
    results = []
    for upload in uploads:
        name = (upload.name or "file.csv")[:200]
        try:
            text, rows = parse_csv_upload(name, upload.read())
            header = csv_header(text)
        except ConnectorError as exc:
            results.append({"name": name, "ok": False, "error": str(exc)})
            continue
        UploadedFile.objects.create(source=source, name=name, content=text, rows=rows, uploaded_by=username)
        results.append({
            "name": name, "ok": True, "rows": rows,
            "missing": [c for c in needed if c not in header],
            "new_columns": [c for c in header if c not in known and c not in needed] if known else [],
            "lumina_ids": _looks_like_lumina_ids(text, mapping.get("id_column")),
        })
        known.update(header)
    return results


def _looks_like_lumina_ids(text, id_column):
    """True when most values of the ID column (or of the first column) are Lumina's own customer IDs. Such a file
    is still read as its own system: its rows join existing customers only by PAN, date of birth, email or mobile."""
    import csv
    import io

    values = []
    for row in csv.DictReader(io.StringIO(text)):
        clean = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        value = clean.get(id_column) if id_column in clean else next(iter(clean.values()), "")
        if value:
            values.append(value)
        if len(values) >= 50:
            break
    return bool(values) and sum(1 for v in values if LUMINA_ID.match(v)) >= 0.8 * len(values)


def _ids_by_file(source):
    """{file id: set of customer IDs in it}, using the mapping's ID column."""
    import csv
    import io

    id_column = (source.mapping or {}).get("id_column")
    found = {}
    for f in source.uploads.all():
        ids = set()
        if id_column:
            for row in csv.DictReader(io.StringIO(f.content)):
                key = (({(k or "").strip(): v for k, v in row.items()}).get(id_column) or "").strip()
                if key:
                    ids.add(key)
        found[f.id] = ids
    return found


@dataclass
class RemovalPlan:
    files: int = 0
    records: int = 0
    customers: int = 0
    conversations: int = 0
    corrections: int = 0


def _doomed(source, file_ids):
    """Customer IDs found only in the files being removed, and the customers only those rows describe."""
    from ingestion.models import SourceRecord
    from mdm.models import Customer, CustomerLink

    by_file = _ids_by_file(source)
    leaving = set().union(*(by_file.get(i, set()) for i in file_ids)) if file_ids else set()
    staying = set().union(*(ids for i, ids in by_file.items() if i not in file_ids)) if by_file else set()
    records = SourceRecord.objects.filter(source=source, source_record_id__in=leaving - staying)
    elsewhere = CustomerLink.objects.exclude(source_record__in=records).values("customer_id")
    customers = Customer.objects.filter(links__source_record__in=records).exclude(id__in=elsewhere).distinct()
    return records, customers


def removal_plan(source, file_ids):
    from interactions.models import Interaction
    from mdm.models import FieldCorrection

    file_ids = set(source.uploads.filter(id__in=file_ids).values_list("id", flat=True))
    records, customers = _doomed(source, file_ids)
    return RemovalPlan(
        files=len(file_ids), records=records.count(), customers=customers.count(),
        conversations=Interaction.objects.filter(customer__in=customers).count(),
        corrections=FieldCorrection.objects.filter(customer__in=customers).count(),
    )


def refresh(source, started_by):
    """Re-read the connector after files changed, then rebuild customers."""
    from ingestion.models import SourceRecord
    from mdm.services import build_customers

    from .sync import sync_source

    if source.enabled and (source.mapping or {}).get("object"):
        if source.uploads.filter(status=UploadedFile.ACTIVE).exists():
            sync_source(source.code, started_by=started_by)
        else:  # every file is suspended or gone: nothing to read, so every row is switched off
            SourceRecord.objects.filter(source=source).update(active=False)
    build_customers()


def set_status(source, file_ids, status, started_by):
    if status not in (UploadedFile.ACTIVE, UploadedFile.SUSPENDED):
        raise ConnectorError("Status must be active or suspended.")
    changed = source.uploads.filter(id__in=file_ids).exclude(status=status).update(status=status)
    if changed:
        refresh(source, started_by)
    return changed


@transaction.atomic
def remove_files(source, file_ids, started_by):
    from ingestion.models import RawRecord
    from interactions.models import Interaction
    from mdm.models import FieldCorrection

    file_ids = set(source.uploads.filter(id__in=file_ids).values_list("id", flat=True))
    plan = removal_plan(source, file_ids)
    records, customers = _doomed(source, file_ids)
    record_ids = list(records.values_list("source_record_id", flat=True))
    customer_ids = list(customers.values_list("id", flat=True))
    FieldCorrection.objects.filter(customer_id__in=customer_ids).delete()
    Interaction.objects.filter(customer_id__in=customer_ids).delete()
    records.delete()  # their golden values, links and match suggestions go with them
    RawRecord.objects.filter(source=source, source_record_id__in=record_ids).delete()
    from mdm.models import Customer

    Customer.objects.filter(id__in=customer_ids).delete()
    source.uploads.filter(id__in=file_ids).delete()
    refresh(source, started_by)
    return plan
