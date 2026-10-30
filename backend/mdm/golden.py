"""Build the golden record and trust score for one customer.

Plain Python, no database code. services.py loads the data and saves the results.

Rule for each field:
  1. The value from the most trusted source wins.
  2. If two sources have equal trust, the most recently updated value wins.
Score = sum over fields of (field weight x trust in the winning value).
Trust in a value grows when other systems hold the same value: two separate systems agreeing are
unlikely to both be wrong, so their trust combines as 1 - (1 - t1) x (1 - t2) x ... Each system counts once;
guessed values never add trust. A field no source holds adds 0.
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
    # A value a system sent always beats one Lumina guessed ("guessed"), then trust, then the newest.
    winner = max(present, key=lambda c: (not c.get("guessed"), c["trust"], c["updated_at"] or OLDEST))
    conflicts = len({c.get("compare") or normalise(c["value"]) for c in present}) - 1
    return {**winner, "score_trust": agreement_trust(winner, present)}, conflicts


def agreement_trust(winner, present):
    """Trust in the winning value, raised by every other system that holds the same value.

    Mobile app (0.60) and core banking (0.80) agreeing: 1 - 0.40 x 0.20 = 0.92. Several records from one
    system count once, at that system's best trust. Approved corrections and guessed values keep their own trust."""
    own = Decimal(str(winner["trust"]))
    if winner.get("correction_id") or winner.get("guessed") or winner.get("source_id") is None:
        return own
    key = winner.get("compare") or normalise(winner["value"])
    best = {winner["source_id"]: own}
    for c in present:
        if c.get("guessed") or c.get("correction_id") or c.get("source_id") is None:
            continue
        if (c.get("compare") or normalise(c["value"])) != key:
            continue
        best[c["source_id"]] = max(best.get(c["source_id"], Decimal(0)), Decimal(str(c["trust"])))
    doubt = Decimal(1)
    for trust in best.values():
        doubt *= Decimal(1) - trust
    return (Decimal(1) - doubt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def trust_score(winners, weights):
    """winners: {field: winner dict or None}. weights: {field: Decimal}. Returns Decimal 0.000 to 1.000."""
    total = sum(
        (weights.get(field, Decimal(0)) * Decimal(str(w.get("score_trust", w["trust"]))) for field, w in winners.items() if w),
        Decimal(0),
    )
    return total.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
