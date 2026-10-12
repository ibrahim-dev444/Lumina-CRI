"""Each organization's own trust settings: how much it trusts each source system, and how much each field
counts in the trust score. Shown and edited as whole numbers from 0 to 100; stored as 0.00 to 1.00."""

from decimal import Decimal

from django.db import transaction

from sources.models import Source

from .models import FIELD_CHOICES, Customer, FieldWeight
from .services import rebuild_golden_record

FIELD_LABELS = dict(FIELD_CHOICES)


class TrustSettingsError(ValueError):
    pass


def _points(value):
    return int((value * 100).to_integral_value())


def get_trust_settings():
    weights = dict(FieldWeight.objects.values_list("field", "weight"))
    return {
        "sources": [
            {"code": s.code, "name": s.name, "category": s.category, "trust": _points(s.trust)}
            for s in Source.objects.order_by("-trust", "name")
        ],
        "weights": [
            {"field": field, "label": label, "points": _points(weights.get(field, Decimal("0")))}
            for field, label in FIELD_CHOICES
        ],
    }


def _whole_number(value, what):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise TrustSettingsError(f"{what} must be a whole number from 0 to 100.")
    return value


@transaction.atomic
def update_trust_settings(sources=None, weights=None):
    """sources: {code: 0-100}; weights: {field: 0-100}, all fields together must add up to 100.
    Saves, then recalculates every customer's golden record and score. Returns the changes for the audit log."""
    changes = {}
    sources = sources or {}
    weights = weights or {}

    known_sources = {s.code: s for s in Source.objects.all()}
    for code, value in sources.items():
        if code not in known_sources:
            raise TrustSettingsError(f"Unknown source: {code}.")
        _whole_number(value, f"Trust for {known_sources[code].name}")

    current = {f: _points(w) for f, w in FieldWeight.objects.values_list("field", "weight")}
    for field, value in weights.items():
        if field not in FIELD_LABELS:
            raise TrustSettingsError(f"Unknown field: {field}.")
        _whole_number(value, f"Points for {FIELD_LABELS[field]}")
    proposed = {field: weights.get(field, current.get(field, 0)) for field in FIELD_LABELS}
    if weights and sum(proposed.values()) != 100:
        raise TrustSettingsError(f"Field points must add up to 100. They add up to {sum(proposed.values())} now.")

    for code, value in sources.items():
        source = known_sources[code]
        if _points(source.trust) != value:
            changes[f"source {code}"] = [_points(source.trust), value]
            source.trust = Decimal(value) / 100
            source.save(update_fields=["trust"])

    for field, value in weights.items():
        if current.get(field) != value:
            changes[f"weight {field}"] = [current.get(field), value]
            FieldWeight.objects.update_or_create(field=field, defaults={"weight": Decimal(value) / 100})

    if changes:
        for customer in Customer.objects.all():
            rebuild_golden_record(customer)
    return changes
