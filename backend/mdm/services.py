"""The mdm module's public functions. Commands, API views and scheduled jobs call these."""

from collections import Counter
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from ingestion.models import SourceRecord
from security.fields import compare_key

from .golden import pick_winner, trust_score
from .matching import find_groups
from .models import FIELDS, Customer, CustomerLink, FieldCorrection, FieldWeight, GoldenField, MatchSuggestion


@dataclass
class BuildResult:
    records: int = 0
    customers: int = 0
    created: int = 0
    merged: int = 0
    new_suggestions: int = 0


def _record_dict(r):
    return {"id": r.id, "name": r.name, "mobile": r.mobile, "email": r.email, "dob": r.dob, "pan": r.pan_hash}


@transaction.atomic
def match_records():
    """Group every source record into customers. Customer IDs stay the same between runs."""
    records = list(SourceRecord.objects.filter(source__enabled=True))
    confirmed = set(
        MatchSuggestion.objects.filter(status=MatchSuggestion.ACCEPTED).values_list("record_a_id", "record_b_id")
    )
    groups, reasons, suggestions = find_groups([_record_dict(r) for r in records], confirmed)

    result = BuildResult(records=len(records), customers=len(groups))
    current = dict(CustomerLink.objects.values_list("source_record_id", "customer_id"))

    used = set()
    for group in groups:
        # Reuse the customer most of these records already belong to, so C-10001 stays C-10001.
        # A customer ID goes to one group only; if a group split, the other part gets a new ID.
        existing = Counter(current[r] for r in group if r in current)
        # Most records first; on a tie the older customer (lower ID) keeps its number.
        free = [c for c, _ in sorted(existing.items(), key=lambda kv: (-kv[1], kv[0])) if c not in used]
        if free:
            customer_id = free[0]
            result.merged += len(free) - 1
        else:
            customer_id = Customer.objects.create().id
            result.created += 1
        used.add(customer_id)
        for record_id in group:
            CustomerLink.objects.update_or_create(
                source_record_id=record_id,
                defaults={"customer_id": customer_id, "match_reason": reasons[record_id]},
            )

    # Customers left with no records (because they were merged into another) are removed.
    # Their corrections move to the customer their records went to, so no approved fix is lost.
    empty = list(Customer.objects.filter(links__isnull=True).values_list("id", flat=True))
    if empty:
        now_linked = dict(CustomerLink.objects.values_list("source_record_id", "customer_id"))
        for old_id in empty:
            moved_to = next((now_linked[r] for r, c in current.items() if c == old_id and r in now_linked), None)
            if moved_to:
                FieldCorrection.objects.filter(customer_id=old_id).update(customer_id=moved_to)
        Customer.objects.filter(id__in=empty, corrections__isnull=True).delete()

    # A pending suggestion is stale once both records already belong to the same customer
    # (for example, a steward merged them through a different pair). Nothing is left to decide.
    linked = dict(CustomerLink.objects.values_list("source_record_id", "customer_id"))
    stale = [
        s.id
        for s in MatchSuggestion.objects.filter(status=MatchSuggestion.PENDING)
        if linked.get(s.record_a_id) is not None and linked.get(s.record_a_id) == linked.get(s.record_b_id)
    ]
    MatchSuggestion.objects.filter(id__in=stale).delete()

    for a, b, points, reason in suggestions:
        a, b = sorted((a, b))
        _, created = MatchSuggestion.objects.get_or_create(
            record_a_id=a, record_b_id=b, defaults={"points": points, "reason": reason}
        )
        result.new_suggestions += created
    return result


@transaction.atomic
def rebuild_golden_record(customer):
    """Recalculate every golden field and the trust score for one customer."""
    weights = dict(FieldWeight.objects.values_list("field", "weight"))
    records = [
        link.source_record
        for link in customer.links.select_related("source_record__source")
        if link.source_record.source.enabled
    ]

    # The latest approved correction per field joins the candidates at trust 1.00.
    corrections = {}
    for c in customer.corrections.filter(status=FieldCorrection.APPROVED).order_by("decided_at", "id"):
        corrections[c.field] = c

    winners = {}
    for field in FIELDS:
        candidates = [
            {
                "value": getattr(r, field),
                "trust": r.source.trust,
                "updated_at": r.source_updated_at,
                "record_id": r.id,
                "source_id": r.source_id,
                "correction_id": None,
                "compare": compare_key(field, getattr(r, field)),
            }
            for r in records
        ]
        if field in corrections:
            c = corrections[field]
            candidates.append({
                "value": c.value,
                "trust": FieldCorrection.TRUST,
                "updated_at": c.decided_at,
                "record_id": None,
                "source_id": None,
                "correction_id": c.id,
                "compare": compare_key(field, c.value),
            })
        winner, conflicts = pick_winner(candidates)
        winners[field] = winner
        if winner:
            GoldenField.objects.update_or_create(
                customer=customer,
                field=field,
                defaults={
                    "value": str(winner["value"]),
                    "trust": winner["trust"],
                    "source_id": winner["source_id"],
                    "source_record_id": winner["record_id"],
                    "correction_id": winner["correction_id"],
                    "conflicts": conflicts,
                },
            )
        else:
            GoldenField.objects.filter(customer=customer, field=field).delete()

    customer.trust_score = trust_score(winners, weights)
    customer.score_updated_at = timezone.now()
    customer.save(update_fields=["trust_score", "score_updated_at"])


def build_customers():
    """Full run: match all records, then rebuild every customer's golden record and score."""
    result = match_records()
    for customer in Customer.objects.all():
        rebuild_golden_record(customer)
    return result


@transaction.atomic
def decide_suggestion(suggestion, accept):
    """A steward's decision. Accepted pairs are merged by the next build_customers() run."""
    suggestion.status = MatchSuggestion.ACCEPTED if accept else MatchSuggestion.REJECTED
    suggestion.decided_at = timezone.now()
    suggestion.save(update_fields=["status", "decided_at"])
