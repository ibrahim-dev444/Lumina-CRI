"""Sign-in lockout: after too many wrong passwords for one username, that username is refused for a while,
even with the right password. Stops someone guessing passwords one after another.

The audit log already records every failed sign-in, so the count comes from there; nothing else is stored.
"""

import math
from datetime import timedelta

from django.utils import timezone

MAX_FAILURES = 5
LOCK_MINUTES = 15


def locked_for(failures, last_success_at=None, now=None):
    """failures: times of failed sign-ins for one username, newest first. Returns minutes left, or 0."""
    now = now or timezone.now()
    window_start = now - timedelta(minutes=LOCK_MINUTES)
    recent = [t for t in failures if t >= window_start and (last_success_at is None or t > last_success_at)]
    if len(recent) < MAX_FAILURES:
        return 0
    unlock_at = recent[0] + timedelta(minutes=LOCK_MINUTES)
    return max(1, math.ceil((unlock_at - now).total_seconds() / 60))


def org_lock_minutes(username):
    """Minutes this username is still locked inside the current organization (0 = not locked)."""
    from audit.models import AuditEvent

    since = timezone.now() - timedelta(minutes=LOCK_MINUTES)
    events = AuditEvent.objects.filter(at__gte=since).order_by("-at")
    failures = list(events.filter(action=AuditEvent.LOGIN_FAILED, actor_name=username).values_list("at", flat=True))
    success = events.filter(action=AuditEvent.LOGIN, actor_name=username).values_list("at", flat=True).first()
    return locked_for(failures, success)


def platform_lock_minutes(username):
    """The same rule for platform logins, counted from the platform activity log."""
    from tenants.models import PlatformEvent

    since = timezone.now() - timedelta(minutes=LOCK_MINUTES)
    events = PlatformEvent.objects.filter(at__gte=since).order_by("-at")
    failures = list(events.filter(action="login_failed", actor_name=username).values_list("at", flat=True))
    success = events.filter(action="login", actor_name=username).values_list("at", flat=True).first()
    return locked_for(failures, success)


def locked_message(minutes):
    return f"Too many wrong passwords. This login is locked for {minutes} more minute{'s' if minutes != 1 else ''}."
