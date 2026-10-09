from rest_framework.permissions import BasePermission

from accounts.roles import can, role_of
from audit.models import AuditEvent
from audit.services import record


class HasRole(BasePermission):
    """Signed in AND given a Lumina role. A new account without a role sees nothing until an admin assigns one."""

    message = "Your account has no Lumina role yet. Ask an administrator to assign one."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and role_of(request.user))


def requires(*capabilities):
    """Permission class: the user needs at least one of these capabilities (see accounts.roles).
    Refusals are written to the audit log."""
    capability = " or ".join(capabilities)

    class Requires(BasePermission):
        message = "Your role does not allow this."

        def has_permission(self, request, view):
            if any(can(request.user, c) for c in capabilities):
                return True
            if request.user and request.user.is_authenticated:
                record(request, AuditEvent.DENIED, target=request.path, capability=capability)
            return False

    Requires.__name__ = "Requires_" + "_or_".join(capabilities)
    return Requires
