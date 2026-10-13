"""Conversations and the "Before you speak" briefing. Every role may read and log them: anyone who talks to a
customer should leave a note for the next colleague. Card and identity numbers in notes are masked on save."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from audit.models import AuditEvent
from audit.services import record
from interactions.briefing import build_briefing
from interactions.models import Interaction
from interactions.services import InteractionError, close_interaction, log_interaction
from mdm.models import Customer, GoldenField

from .permissions import HasRole


def interaction_json(i, with_customer=False):
    data = {
        "id": i.id,
        "channel": i.channel,
        "channel_label": i.get_channel_display(),
        "inbound": i.inbound,
        "kind": i.kind,
        "kind_label": i.get_kind_display(),
        "summary": i.summary,
        "outcome": i.outcome,
        "outcome_label": i.get_outcome_display(),
        "follow_up_on": i.follow_up_on.isoformat() if i.follow_up_on else None,
        "state": i.state,
        "created_at": i.created_at.isoformat(),
        "created_by": i.created_by_name,
        "closed_at": i.closed_at.isoformat() if i.closed_at else None,
        "closed_by": i.closed_by_name,
        "closing_note": i.closing_note,
    }
    if with_customer:
        name = GoldenField.objects.filter(customer_id=i.customer_id, field="name").values_list("value", flat=True)
        data["customer"] = {"id": i.customer_id, "code": i.customer.code, "name": name.first() or ""}
    return data


@api_view(["GET", "POST"])
@permission_classes([HasRole])
def customer_interactions(request, pk):
    """GET  /api/customers/<id>/interactions/  newest first (50)
    POST /api/customers/<id>/interactions/  {channel, kind, summary, outcome, inbound?, follow_up_on?}"""
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "GET":
        return Response([interaction_json(i) for i in customer.interactions.all()[:50]])
    d = request.data
    try:
        item = log_interaction(customer, request.user, d.get("channel"), d.get("kind"), d.get("summary"),
                               d.get("outcome"), inbound=d.get("inbound", True), follow_up_on=d.get("follow_up_on"))
    except InteractionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    # The note itself is not copied to the audit log; it stays with the customer.
    record(request, AuditEvent.INTERACTION_LOGGED, target=customer.code, channel=item.channel, kind=item.kind,
           outcome=item.outcome, interaction=item.id)
    return Response(interaction_json(item), status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([HasRole])
def customer_briefing(request, pk):
    """GET /api/customers/<id>/briefing/  What to know before speaking to this customer."""
    customer = get_object_or_404(Customer, pk=pk)
    return Response(build_briefing(customer, request.user))


@api_view(["POST"])
@permission_classes([HasRole])
def close(request, pk):
    """POST /api/interactions/<id>/close/  {note}  Closes a complaint or follow-up."""
    item = get_object_or_404(Interaction, pk=pk)
    try:
        close_interaction(item, request.user, request.data.get("note"))
    except InteractionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    record(request, AuditEvent.INTERACTION_CLOSED, target=item.customer.code, interaction=item.id)
    return Response(interaction_json(item))


@api_view(["GET"])
@permission_classes([HasRole])
def open_items(request):
    """GET /api/interactions/open/  Open complaints and follow-ups across all customers, oldest first."""
    items = Interaction.objects.filter(state=Interaction.OPEN).select_related("customer").order_by("created_at")
    return Response([interaction_json(i, with_customer=True) for i in items[:200]])
