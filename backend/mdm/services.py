"""The mdm module's public functions. Commands, API views and scheduled jobs call these."""

from collections import Counter
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from ingestion.models import SourceRecord
from interactions.models import Interaction
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
    records = list(SourceRecord.objects.filter(source__enabled=True, active=True))
    confirmed = set(
        MatchSuggestion.objects.filter(status=MatchSuggestion.ACCEPTED).values_list("record_a_id", "record_b_id")
    )
    groups, reasons, suggestions = find_groups([_record_dict(r) for r in records], confirmed)

    result = BuildResult(records=len(records), customers=len(groups))
    current = dict(CustomerLink.objects.values_list("source_record_id", "customer_id"))

    used, owner, needs_new = set(), {}, []
    for group in groups:
        # Reuse the customer most of these records already belong to, so C-10001 stays C-10001.
        # A customer ID goes to one group only; if a group split, the other part gets a new ID.
        existing = Counter(current[r] for r in group if r in current)
        # Most records first; on a tie the older customer (lower ID) keeps its number.
        free = [c for c, _ in sorted(existing.items(), key=lambda kv: (-kv[1], kv[0])) if c not in used]
        if free:
            used.add(free[0])
            result.merged += len(free) - 1
            for record_id in group:
                owner[record_id] = free[0]
        else:
            needs_new.append(group)
    # New customers in one insert, then every link written in bulk: a few queries whatever the size.
    fresh = Customer.objects.bulk_create([Customer() for _ in needs_new])
    result.created += len(fresh)
    for group, customer in zip(needs_new, fresh):
        for record_id in group:
            owner[record_id] = customer.id
    links = {link.source_record_id: link for link in CustomerLink.objects.filter(source_record_id__in=list(owner))}
    to_create, to_update = [], []
    for record_id, customer_id in owner.items():
        link = links.get(record_id)
        if link is None:
            to_create.append(CustomerLink(source_record_id=record_id, customer_id=customer_id,
                                          match_reason=reasons[record_id]))
        elif link.customer_id != customer_id or link.match_reason != reasons[record_id]:
            link.customer_id, link.match_reason = customer_id, reasons[record_id]
            to_update.append(link)
    CustomerLink.objects.bulk_create(to_create, batch_size=1000)
    CustomerLink.objects.bulk_update(to_update, ["customer", "match_reason"], batch_size=1000)

    # Customers left with no records (because they were merged into another) are removed.
    # Their corrections and conversations move to the customer their records went to, so nothing is lost.
    empty = list(Customer.objects.filter(links__isnull=True).values_list("id", flat=True))
    if empty:
        now_linked = dict(CustomerLink.objects.values_list("source_record_id", "customer_id"))
        for old_id in empty:
            moved_to = next((now_linked[r] for r, c in current.items() if c == old_id and r in now_linked), None)
            if moved_to:
                FieldCorrection.objects.filter(customer_id=old_id).update(customer_id=moved_to)
                Interaction.objects.filter(customer_id=old_id).update(customer_id=moved_to)
        Customer.objects.filter(id__in=empty, corrections__isnull=True, interactions__isnull=True).delete()

    # A pending suggestion is stale once both records already belong to the same customer
    # (for example, a steward merged them through a different pair). Nothing is left to decide.
    linked = dict(CustomerLink.objects.values_list("source_record_id", "customer_id"))
    stale = [
        s.id
        for s in MatchSuggestion.objects.filter(status=MatchSuggestion.PENDING)
        if linked.get(s.record_a_id) is not None and linked.get(s.record_a_id) == linked.get(s.record_b_id)
    ]
    MatchSuggestion.objects.filter(id__in=stale).delete()

    known = set(MatchSuggestion.objects.values_list("record_a_id", "record_b_id"))
    new = {}
    for a, b, points, reason in suggestions:
        a, b = sorted((a, b))
        if (a, b) not in known and (a, b) not in new:
            new[(a, b)] = MatchSuggestion(record_a_id=a, record_b_id=b, points=points, reason=reason)
    MatchSuggestion.objects.bulk_create(new.values(), batch_size=1000, ignore_conflicts=True)
    result.new_suggestions = len(new)
    return result


def rebuild_golden_record(customer):
    """Recalculate every golden field and the trust score for one customer."""
    rebuild_customers([customer.id])
    customer.refresh_from_db(fields=["trust_score", "score_updated_at", "pan_hash"])


@transaction.atomic
def rebuild_customers(customer_ids=None):
    """Recalculate golden fields and trust scores for these customers (all when None). Everything is read in a
    few queries and only changed values are written, so a full rebuild stays quick with thousands of customers."""
    weights = dict(FieldWeight.objects.values_list("field", "weight"))
    customers = Customer.objects.all() if customer_ids is None else Customer.objects.filter(id__in=customer_ids)
    customers = list(customers)
    ids = [c.id for c in customers]

    records = {}
    for link in CustomerLink.objects.filter(customer_id__in=ids).select_related("source_record__source"):
        r = link.source_record
        if r.source.enabled and r.active:
            records.setdefault(link.customer_id, []).append(r)
    corrections = {}  # the latest approved correction per customer and field joins at trust 1.00
    approved = FieldCorrection.objects.filter(customer_id__in=ids, status=FieldCorrection.APPROVED)
    for c in approved.order_by("decided_at", "id"):
        corrections[(c.customer_id, c.field)] = c
    existing = {(g.customer_id, g.field): g for g in GoldenField.objects.filter(customer_id__in=ids)}

    to_create, to_update, to_delete = [], [], []
    now = timezone.now()
    for customer in customers:
        mine = records.get(customer.id, [])
        winners = {}
        for field in FIELDS:
            candidates = [
                {
                    "value": getattr(r, field),
                    "trust": r.source.trust_for(field),
                    "updated_at": r.source_updated_at,
                    "record_id": r.id,
                    "source_id": r.source_id,
                    "correction_id": None,
                    "compare": compare_key(field, getattr(r, field)),
                }
                for r in mine
            ]
            c = corrections.get((customer.id, field))
            if c:
                candidates.append({
                    "value": c.value, "trust": FieldCorrection.TRUST, "updated_at": c.decided_at,
                    "record_id": None, "source_id": None, "correction_id": c.id,
                    "compare": compare_key(field, c.value),
                })
            winner, conflicts = pick_winner(candidates)
            winners[field] = winner
            current = existing.get((customer.id, field))
            if not winner:
                if current:
                    to_delete.append(current.id)
                continue
            wanted = {"value": str(winner["value"]), "trust": winner["trust"], "source_id": winner["source_id"],
                      "source_record_id": winner["record_id"], "correction_id": winner["correction_id"],
                      "conflicts": conflicts}
            if current is None:
                to_create.append(GoldenField(customer_id=customer.id, field=field, **wanted))
            elif any(getattr(current, k) != v for k, v in wanted.items()):
                for k, v in wanted.items():
                    setattr(current, k, v)
                to_update.append(current)
        customer.trust_score = trust_score(winners, weights)
        customer.score_updated_at = now
        customer.pan_hash = winners["pan"]["compare"] if winners.get("pan") else ""

    GoldenField.objects.filter(id__in=to_delete).delete()
    GoldenField.objects.bulk_create(to_create, batch_size=1000)
    GoldenField.objects.bulk_update(to_update, ["value", "trust", "source", "source_record", "correction",
                                                "conflicts"], batch_size=1000)
    Customer.objects.bulk_update(customers, ["trust_score", "score_updated_at", "pan_hash"], batch_size=1000)


def build_customers():
    """Full run: match all records, then rebuild every customer's golden record and score."""
    result = match_records()
    rebuild_customers()
    return result


@transaction.atomic
def decide_suggestion(suggestion, accept):
    """A steward's decision. Accepted pairs are merged by the next build_customers() run."""
    suggestion.status = MatchSuggestion.ACCEPTED if accept else MatchSuggestion.REJECTED
    suggestion.decided_at = timezone.now()
    suggestion.save(update_fields=["status", "decided_at"])
