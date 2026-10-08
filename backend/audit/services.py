from accounts.roles import role_of

from .models import AuditEvent


def _client_ip(request):
    # Behind a proxy the real address is the first entry of X-Forwarded-For; only trust it once a
    # proxy we control sets it. For now we record the direct connection address.
    return request.META.get("REMOTE_ADDR") or None


def record(request, action, target="", user=None, **detail):
    """Write one audit event for the current request. `user` overrides request.user (e.g. at login)."""
    actor = user if user is not None else getattr(request, "user", None)
    signed_in = actor is not None and actor.is_authenticated
    return AuditEvent.objects.create(
        actor=actor if signed_in else None,
        actor_name=actor.get_username() if signed_in else str(detail.pop("username", "") or "anonymous"),
        role=(role_of(actor) or "") if signed_in else "",
        action=action,
        target=target,
        detail=detail,
        ip=_client_ip(request),
    )
