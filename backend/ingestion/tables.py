"""Several customer tables on one database connector: add a table with its own column mapping, suspend or resume
tables, and remove added tables.

The connector's first table is its main table (its mapping and the accounts table belong to it); added tables
live in mapping["tables"]. A sync reads every active table. Suspending switches off the rows of that table
without deleting them, so resuming brings back the same customers with the same IDs. Only added tables can be
removed; to drop the main table, delete the connector.
"""

from dataclasses import dataclass

from django.db import transaction

from mdm.models import FIELDS

from .connectors.adapters import ConnectorError
from .connectors.catalog import adapter_for
from .connectors.generic import MAIN, customer_tables

ACTIVE, SUSPENDED = "active", "suspended"


def _clean(data, columns):
    obj = str(data.get("object") or "").strip()
    id_column = str(data.get("id_column") or "").strip()
    updated_column = str(data.get("updated_column") or "").strip()
    fields = {k: v for k, v in (data.get("fields") or {}).items() if v}
    unknown = [f for f in fields if f not in FIELDS]
    if unknown:
        raise ConnectorError(f"Unknown Lumina field(s): {', '.join(unknown)}.")
    if not obj or not id_column:
        raise ConnectorError("Choose the table and which column is the record ID.")
    if not fields.get("name"):
        raise ConnectorError("Map at least the customer name.")
    used = [id_column, *fields.values()] + ([updated_column] if updated_column else [])
    missing = [c for c in used if c not in columns]
    if missing:
        raise ConnectorError(f"{', '.join(missing)} not found in {obj}.")
    return {"object": obj, "id_column": id_column, "updated_column": updated_column, "fields": fields}


def save_table(source, data, key=None):
    """Add a customer table (key None) or change an added one. Returns its key."""
    mapping = dict(source.mapping or {})
    if not mapping.get("object"):
        raise ConnectorError("Map the main customer table first.")
    obj = str(data.get("object") or "").strip()
    table = _clean(data, adapter_for(source).list_columns(obj) if obj else [])
    tables = [dict(t) for t in mapping.get("tables") or []]
    if any(t["object"] == table["object"] and t["key"] != key for t in tables) or \
            (mapping["object"] == table["object"]):
        raise ConnectorError(f"{table['object']} is already one of this connector's tables.")
    if key is None:
        taken = {t["key"] for t in tables}
        key = next(f"t{n}" for n in range(2, 100) if f"t{n}" not in taken)
        tables.append({"key": key, **table, "status": ACTIVE})
    else:
        match = next((t for t in tables if t["key"] == key), None)
        if match is None:
            raise ConnectorError("No such table on this connector.")
        match.update(table)
    mapping["tables"] = tables
    source.mapping = mapping
    source.save(update_fields=["mapping"])
    return key


def set_table_status(source, keys, status, started_by):
    if status not in (ACTIVE, SUSPENDED):
        raise ConnectorError("Status must be active or suspended.")
    mapping = dict(source.mapping or {})
    changed = 0
    if MAIN in keys and (mapping.get("status") or ACTIVE) != status:
        mapping["status"] = status
        changed += 1
    tables = [dict(t) for t in mapping.get("tables") or []]
    for t in tables:
        if t["key"] in keys and t.get("status", ACTIVE) != status:
            t["status"] = status
            changed += 1
    if changed:
        mapping["tables"] = tables
        source.mapping = mapping
        source.save(update_fields=["mapping"])
        refresh(source, started_by)
    return changed


def refresh(source, started_by):
    """Re-read the connector after its tables changed, then rebuild customers."""
    from ingestion.models import SourceRecord
    from mdm.services import build_customers

    from .sync import sync_source

    if source.enabled and (source.mapping or {}).get("object"):
        if any(t["status"] == ACTIVE for t in customer_tables(source.mapping)):
            sync_source(source.code, started_by=started_by)
        else:  # every table is suspended: nothing to read, so every row is switched off
            SourceRecord.objects.filter(source=source).update(active=False)
    build_customers()


@dataclass
class RemovalPlan:
    tables: int = 0
    records: int = 0
    customers: int = 0
    conversations: int = 0
    corrections: int = 0


def _doomed(source, keys):
    from ingestion.models import SourceRecord
    from mdm.models import Customer, CustomerLink

    records = SourceRecord.objects.filter(source=source, origin_table__in=keys)
    elsewhere = CustomerLink.objects.exclude(source_record__in=records).values("customer_id")
    customers = Customer.objects.filter(links__source_record__in=records).exclude(id__in=elsewhere).distinct()
    return records, customers


def _removable(source, keys):
    if MAIN in keys:
        raise ConnectorError("The main table cannot be removed. Suspend it, or delete the connector.")
    known = {t["key"] for t in (source.mapping or {}).get("tables") or []}
    return [k for k in keys if k in known]


def removal_plan(source, keys):
    from interactions.models import Interaction
    from mdm.models import FieldCorrection

    keys = _removable(source, keys)
    records, customers = _doomed(source, keys)
    return RemovalPlan(
        tables=len(keys), records=records.count(), customers=customers.count(),
        conversations=Interaction.objects.filter(customer__in=customers).count(),
        corrections=FieldCorrection.objects.filter(customer__in=customers).count(),
    )


@transaction.atomic
def remove_tables(source, keys, started_by):
    from ingestion.models import RawRecord
    from interactions.models import Interaction
    from mdm.models import Customer, FieldCorrection

    keys = _removable(source, keys)
    plan = removal_plan(source, keys)
    records, customers = _doomed(source, keys)
    record_ids = list(records.values_list("source_record_id", flat=True))
    customer_ids = list(customers.values_list("id", flat=True))
    FieldCorrection.objects.filter(customer_id__in=customer_ids).delete()
    Interaction.objects.filter(customer_id__in=customer_ids).delete()
    records.delete()
    RawRecord.objects.filter(source=source, source_record_id__in=record_ids).delete()
    Customer.objects.filter(id__in=customer_ids).delete()
    mapping = dict(source.mapping or {})
    mapping["tables"] = [t for t in mapping.get("tables") or [] if t["key"] not in keys]
    source.mapping = mapping
    source.save(update_fields=["mapping"])
    refresh(source, started_by)
    return plan
