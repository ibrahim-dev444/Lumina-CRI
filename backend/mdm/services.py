"""The mdm module's public functions. Commands, API views and scheduled jobs call these."""

from collections import Counter
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from ingestion.models import SourceRecord

from .golden import pick_winner, trust_score
from .matching import find_groups
from .models import FIELDS, Customer, CustomerLink, FieldWeight, GoldenField, MatchSuggestion


@dataclass
class BuildResult:
    records: int = 0
    customers: int = 0
    created: int = 0
    merged: int = 0
    new_suggestions: int = 0


def _record_dict(r):
    return {"id": r.id, "name": r.name, "mobile": r.mobile, "email": r.email, "dob": r.dob}


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
        free = [c for c, _ in existing.most_common() if c not in used]
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
    Customer.objects.filter(links__isnull=True).delete()

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

    winners = {}
    for field in FIELDS:
        candidates = [
            {
                "value": getattr(r, field),
                "trust": r.source.trust,
                "updated_at": r.source_updated_at,
                "record_id": r.id,
                "source_id": r.source_id,
            }
            for r in records
        ]
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
