"""Conversations with a customer: calls, emails, chats and branch visits, logged by the bank's staff.

Each one belongs to a golden customer. When customers are merged, matching moves their conversations along
with their corrections (mdm/services.py), so nothing a colleague wrote is lost. Complaints and follow-ups stay
open until someone closes them, which is what the "Before you speak" briefing warns about.
"""

from django.conf import settings
from django.db import models

from mdm.models import Customer

CHANNELS = [
    ("call", "Phone call"),
    ("branch", "Branch visit"),
    ("email", "Email"),
    ("whatsapp", "WhatsApp"),
    ("chat", "Chat"),
    ("sms", "SMS"),
]
KINDS = [
    ("query", "Question"),
    ("request", "Service request"),
    ("complaint", "Complaint"),
    ("sales", "Sales conversation"),
    ("feedback", "Feedback"),
]
OUTCOMES = [
    ("resolved", "Resolved"),
    ("follow_up", "Needs a follow-up"),
    ("escalated", "Escalated"),
]


class Interaction(models.Model):
    OPEN, CLOSED = "open", "closed"

    # PROTECT: a customer with conversations is never deleted by accident; merges move them instead.
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="interactions")
    channel = models.CharField(max_length=10, choices=CHANNELS)
    inbound = models.BooleanField(default=True)  # the customer contacted the bank
    kind = models.CharField(max_length=10, choices=KINDS)
    summary = models.TextField(max_length=600)  # card and identity numbers are masked before saving
    outcome = models.CharField(max_length=10, choices=OUTCOMES)
    follow_up_on = models.DateField(null=True, blank=True)
    # Complaints, follow-ups and escalations are open until someone closes them.
    state = models.CharField(max_length=6, choices=[(OPEN, "Open"), (CLOSED, "Closed")], default=CLOSED,
                             db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_by_name = models.CharField(max_length=150)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_name = models.CharField(max_length=150, blank=True)
    closing_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.customer.code} {self.get_kind_display()} by {self.get_channel_display()} ({self.state})"
