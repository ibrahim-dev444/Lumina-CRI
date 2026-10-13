"""Logging and closing conversations. The API calls these; the rules live here."""

import re
from datetime import date

from django.utils import timezone

from .models import CHANNELS, KINDS, OUTCOMES, Interaction


class InteractionError(ValueError):
    pass


# Staff sometimes type a card or account number into a note. Never keep it: keep the last four only.
_LONG_NUMBER = re.compile(r"(?<![0-9])(?:[0-9][ -]?){11,18}[0-9](?![0-9])")
_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_AADHAAR = re.compile(r"(?<![0-9])[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}(?![0-9])")


def mask_numbers(text):
    """'card 4111 1111 1111 1234' -> 'card XXXX1234'; PANs and Aadhaar numbers are hidden too."""
    def last4(match):
        digits = re.sub(r"[^0-9]", "", match.group(0))
        return f"XXXX{digits[-4:]}"

    text = _LONG_NUMBER.sub(last4, text)  # cards and accounts first, so a card is never read as an Aadhaar
    text = _AADHAAR.sub(last4, text)
    return _PAN.sub("[PAN hidden]", text)


def log_interaction(customer, user, channel, kind, summary, outcome, inbound=True, follow_up_on=None):
    if channel not in dict(CHANNELS):
        raise InteractionError("Choose how the customer was contacted.")
    if kind not in dict(KINDS):
        raise InteractionError("Choose what the conversation was about.")
    if outcome not in dict(OUTCOMES):
        raise InteractionError("Choose the outcome.")
    summary = mask_numbers(" ".join(str(summary or "").split()))
    if len(summary) < 10:
        raise InteractionError("Write a short summary (at least 10 characters).")
    if len(summary) > 600:
        raise InteractionError("Keep the summary under 600 characters.")
    if follow_up_on:
        try:
            follow_up_on = date.fromisoformat(str(follow_up_on))
        except ValueError as exc:
            raise InteractionError("Follow-up date must look like 2026-10-20.") from exc
        if follow_up_on < timezone.localdate():
            raise InteractionError("The follow-up date cannot be in the past.")
    if outcome == "follow_up" and not follow_up_on:
        raise InteractionError("Pick the date for the follow-up.")
    # Something is left to do unless the conversation ended resolved.
    still_open = outcome != "resolved"
    return Interaction.objects.create(
        customer=customer, channel=channel, kind=kind, summary=summary, outcome=outcome,
        inbound=bool(inbound), follow_up_on=follow_up_on or None,
        state=Interaction.OPEN if still_open else Interaction.CLOSED,
        created_by=user, created_by_name=user.get_username(),
    )


def close_interaction(interaction, user, note):
    if interaction.state == Interaction.CLOSED:
        raise InteractionError("This is already closed.")
    note = mask_numbers(" ".join(str(note or "").split()))
    if len(note) < 5:
        raise InteractionError("Say how it was closed (at least 5 characters).")
    interaction.state = Interaction.CLOSED
    interaction.closed_at = timezone.now()
    interaction.closed_by_name = user.get_username()
    interaction.closing_note = note[:300]
    interaction.save(update_fields=["state", "closed_at", "closed_by_name", "closing_note"])
    return interaction
