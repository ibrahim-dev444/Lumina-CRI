""""Before you speak": what a colleague should know in the ten seconds before a call or a meeting.

Built from what Lumina already holds: open complaints and follow-ups, products (Phase E), KYC and consent,
duplicates waiting for review and fields the sources disagree on. Every warning says what to do about it.

Front-line staff must never learn about AML risk, politically exposed person flags or sanctions results
("tipping off" is an offence), so those appear only for roles with view_compliance, marked as not to be shared.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from accounts.roles import can
from compliance.models import KycRecord
from compliance.services import current_consents
from mdm.models import GoldenField, MatchSuggestion
from products.models import CLOSED, CREDIT_CARD, DEPOSIT, DORMANT, HOME_LOAN, LOANS, OVERDUE, SAVINGS
from products.services import holdings_for

from .models import Interaction

BAD, WARN, INFO = "bad", "warn", "info"


def _rupees(amount):
    """1245000 -> '₹12,45,000' (Indian grouping)."""
    whole = f"{int(round(amount)):d}"
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail]) if groups else f"₹{tail}"


def _raised(since):
    days = (timezone.now() - since).days
    return "raised today" if days == 0 else "raised yesterday" if days == 1 else f"open {days} days"


def _and(words):
    """['address', 'email', 'mobile'] -> 'address, email and mobile'."""
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def build_briefing(customer, user):
    today = timezone.localdate()
    amounts = can(user, "view_balances")
    alerts, points = [], []

    def alert(level, title, action, kind):
        alerts.append({"level": level, "title": title, "action": action, "kind": kind})

    # Conversations that are still open come first: the customer will bring them up.
    open_items = list(customer.interactions.filter(state=Interaction.OPEN).order_by("created_at"))
    for item in open_items:
        if item.kind == "complaint":
            alert(BAD, f"Complaint {_raised(item.created_at)}: {item.summary[:90]}",
                  "Acknowledge it first and give an update before anything else.", "complaint")
        elif item.follow_up_on and item.follow_up_on < today:
            alert(BAD, f"Follow-up promised for {item.follow_up_on:%d %b} was missed: {item.summary[:80]}",
                  "Apologise for the delay and close it on this call if you can.", "follow_up")
        else:
            when = f"due {item.follow_up_on:%d %b}" if item.follow_up_on else "open"
            alert(WARN, f"Follow-up {when}: {item.summary[:90]}", "Check whether this call settles it.",
                  "follow_up")

    holdings = [h for h in holdings_for(customer) if h.status != CLOSED]
    for h in holdings:
        name = h.product_name or h.get_product_type_display()
        if h.status == OVERDUE:
            owed = f" ({_rupees(h.balance)} outstanding)" if amounts and h.balance is not None else ""
            alert(BAD, f"{name} is overdue{owed}.",
                  "Mention the overdue payment politely and offer the payment options.", "overdue")
        elif h.status == DORMANT:
            alert(WARN, f"{name} is dormant.", "Ask whether they still use it; reactivation needs fresh KYC.",
                  "dormant")

    kyc = KycRecord.objects.filter(pan_hash=customer.pan_hash).first() if customer.pan_hash else None
    if kyc:
        status = kyc.status(today)
        if status == "overdue":
            alert(BAD, "Re-KYC is overdue.", "Ask for updated KYC documents before any new request.", "kyc")
        elif status == "due_soon":
            alert(WARN, f"Re-KYC is due on {kyc.re_kyc_due:%d %b %Y}.",
                  "Remind the customer to submit updated documents.", "kyc")
        if can(user, "view_compliance") and (kyc.pep or kyc.sanctions == KycRecord.POTENTIAL_MATCH
                                             or kyc.risk == KycRecord.HIGH):
            flags = [label for label, on in [("high AML risk", kyc.risk == KycRecord.HIGH),
                                              ("politically exposed", kyc.pep),
                                              ("possible sanctions match", kyc.sanctions == KycRecord.POTENTIAL_MATCH)]
                     if on]
            alert(BAD, f"Compliance: {', '.join(flags)}.",
                  "Internal only. Never mention this to the customer.", "compliance")
    elif not customer.pan_hash:
        alert(WARN, "No PAN on file.", "Ask for the PAN before opening any product or changing details.", "pan")

    records = list(customer.links.values_list("source_record_id", flat=True))
    if records and MatchSuggestion.objects.filter(
        Q(record_a_id__in=records) | Q(record_b_id__in=records), status=MatchSuggestion.PENDING
    ).exists():
        alert(WARN, "Another record may be the same person.",
              "Confirm date of birth and mobile; a data steward is reviewing the duplicate.", "duplicate")

    disputed = [g.get_field_display().lower() for g in GoldenField.objects.filter(
        customer=customer, field__in=["mobile", "email", "address"], conflicts__gt=0)]
    if disputed:
        alert(WARN, f"Systems disagree on the {_and(disputed)}.",
              "Confirm it with the customer before sending anything there.", "conflict")

    consents = current_consents(customer.pan_hash)
    marketing = consents["marketing"].status if consents["marketing"] else "unknown"
    cross_sell = consents["cross_sell"].status if consents["cross_sell"] else "unknown"
    if marketing == "revoked" or cross_sell == "revoked":
        alert(INFO, "Do not offer new products.", "The customer withdrew consent for marketing or cross-sell.",
              "consent")

    # Talking points: what they hold, then gentle ideas when they agreed to hear offers.
    types = {h.product_type for h in holdings}
    for h in sorted(holdings, key=lambda h: h.opened_on or today):
        since = f" since {h.opened_on:%Y}" if h.opened_on else ""
        points.append(f"Holds {h.product_name or h.get_product_type_display()}{since}.")
    if cross_sell == "granted" and not any(a["kind"] in ("overdue", "complaint") for a in alerts):
        if SAVINGS in types and DEPOSIT not in types:
            points.append("Could discuss a fixed deposit for idle savings.")
        if HOME_LOAN in types and CREDIT_CARD not in types:
            points.append("Home loan customer without a card: a credit card may suit them.")
        if not types & LOANS and SAVINGS in types:
            points.append("No loans with the bank: pre-approved offers may apply.")

    last = customer.interactions.order_by("-created_at").first()
    order = {BAD: 0, WARN: 1, INFO: 2}
    alerts.sort(key=lambda a: order[a["level"]])
    return {
        "headline": _headline(alerts),
        "alerts": alerts,
        "talking_points": points[:6],
        "last_contact": {
            "at": last.created_at.isoformat(),
            "channel": last.get_channel_display(),
            "by": last.created_by_name,
            "summary": last.summary,
        } if last else None,
        "contacts_last_90_days": customer.interactions.filter(
            created_at__gte=timezone.now() - timedelta(days=90)).count(),
        "open_items": len(open_items),
    }


def _headline(alerts):
    bad = sum(1 for a in alerts if a["level"] == BAD)
    if bad:
        return f"{bad} thing{'s' if bad > 1 else ''} to handle first"
    if alerts:
        return "Good to talk, with a few things to check"
    return "Nothing to flag. Good to talk."
