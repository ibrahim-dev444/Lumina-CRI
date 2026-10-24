"""Trust per field for one connector, set by an organization administrator after mapping.

A core banking system can be trusted for PAN and date of birth but not for a mobile number its branches rarely
update; a CRM the other way round. Each field a connector maps gets its own trust (0-100); a field without one
uses the connector's default trust. Saving recalculates every customer's golden record and trust score.
"""

from django.db import transaction

from ingestion.connectors.generic import customer_tables

from .models import FIELDS
from .services import rebuild_customers
from .trust_settings import FIELD_LABELS, TrustSettingsError, _points, _whole_number


def mapped_fields(source):
    """The Lumina fields this connector supplies, in display order. Push connectors and the built-in demo
    connectors can send every field; mapped connectors send the fields their tables map."""
    if source.connector_type == "push_api" or source.connector_type.startswith("demo") or not source.connector_type:
        return list(FIELDS)
    found = {field for table in customer_tables(source.mapping) for field in (table.get("fields") or {})}
    return [f for f in FIELDS if f in found]


def get_field_trust(source):
    own = source.field_trust or {}
    return {
        "code": source.code,
        "name": source.name,
        "default": _points(source.trust),
        "fields": [
            {"field": f, "label": FIELD_LABELS[f], "trust": own.get(f, _points(source.trust)), "own": f in own}
            for f in mapped_fields(source)
        ],
    }


@transaction.atomic
def set_field_trust(source, trust):
    """trust: {field: 0-100} for fields this connector maps. Returns the changes for the audit log."""
    if not isinstance(trust, dict) or not trust:
        raise TrustSettingsError("Choose one or more fields and a trust from 0 to 100.")
    allowed = set(mapped_fields(source))
    for field, value in trust.items():
        if field not in allowed:
            raise TrustSettingsError(f"{source.name} does not supply {FIELD_LABELS.get(field, field)}.")
        _whole_number(value, f"Trust for {FIELD_LABELS[field]}")

    own = dict(source.field_trust or {})
    changes = {}
    for field, value in trust.items():
        before = own.get(field, _points(source.trust))
        if before != value or field not in own:
            own[field] = value
            if before != value:
                changes[field] = [before, value]
    source.field_trust = own
    source.save(update_fields=["field_trust"])
    if changes:
        rebuild_customers()
    return changes
