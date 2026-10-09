"""Build the golden record and trust score for one customer.

Plain Python, no database code. services.py loads the data and saves the results.

Rule for each field:
  1. The value from the most trusted source wins.
  2. If two sources have equal trust, the most recently updated value wins.
Score = sum over fields of (field weight x trust of the winning source).
A field no source holds adds 0.
"""

import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

OLDEST = datetime.min.replace(tzinfo=timezone.utc)


def normalise(value):
    """For counting conflicts: 'Suresh Kumar' and 'suresh  kumar' are the same value."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def pick_winner(candidates):
    """candidates: list of dicts with value, trust, updated_at (may be None), record_id, source_id.
    An optional "compare" key says what to compare when counting conflicts (encrypted values pass
    their fingerprint here, because two encryptions of the same PAN never look alike).

    Returns (winner or None, number of other different values).
    """
    present = [c for c in candidates if c["value"] not in (None, "")]
    if not present:
        return None, 0
    winner = max(present, key=lambda c: (c["trust"], c["updated_at"] or OLDEST))
    conflicts = len({c.get("compare") or normalise(c["value"]) for c in present}) - 1
    return winner, conflicts


def trust_score(winners, weights):
    """winners: {field: winner dict or None}. weights: {field: Decimal}. Returns Decimal 0.000 to 1.000."""
    total = sum(
        (weights.get(field, Decimal(0)) * Decimal(w["trust"]) for field, w in winners.items() if w),
        Decimal(0),
    )
    return total.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
