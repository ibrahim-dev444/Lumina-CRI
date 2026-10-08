from rest_framework.permissions import BasePermission

from accounts.roles import can, role_of
from audit.models import AuditEvent
from audit.services import record


class HasRole(BasePermission):
    """Signed in AND given a Lumina role. A new account without a role sees nothing until an admin assigns one."""

    message = "Your account has no Lumina role yet. Ask an administrator to assign one."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and role_of(request.user))


def requires(capability):
    """Permission class for one capability from accounts.roles. Refusals are written to the audit log."""

    class Requires(BasePermission):
        message = "Your role does not allow this."

        def has_permission(self, request, view):
            if can(request.user, capability):
                return True
            if request.user and request.user.is_authenticated:
                record(request, AuditEvent.DENIED, target=request.path, capability=capability)
            return False

    Requires.__name__ = f"Requires_{capability}"
    return Requires
