"""The organization administrator's screens: people and roles, trust settings, logo, and anyone's own password.

Everything runs inside the organization's own schema, so an administrator only ever manages their own bank.
"""

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.services import (
    UserAdminError,
    change_own_password,
    create_user,
    list_users,
    reset_password,
    update_user,
    user_json,
)
from audit.models import AuditEvent
from audit.services import record
from mdm.trust_settings import TrustSettingsError, get_trust_settings, update_trust_settings
from tenants.logo import LogoError, clean_logo

from .permissions import HasRole, requires


def _yes_no(value):
    """true/false from JSON (or "true"/"false" from a form); None when not given."""
    if value is None or isinstance(value, bool):
        return value
    if str(value).lower() in ("true", "false"):
        return str(value).lower() == "true"
    raise UserAdminError("Active must be true or false.")


class UserViewSet(viewsets.ViewSet):
    """GET/POST /api/users/, PATCH /api/users/<id>/, POST /api/users/<id>/reset-password/ (administrators only)."""

    permission_classes = [HasRole, requires("manage_users")]

    def list(self, request):
        return Response([user_json(u) for u in list_users()])

    def create(self, request):
        data = request.data
        try:
            user, password = create_user(
                request.user, data.get("username"), data.get("first_name"), data.get("last_name"), data.get("role")
            )
        except UserAdminError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        record(request, AuditEvent.USER_CREATED, target=user.username, role_given=data.get("role"))
        # The temporary password is returned once, to show the administrator. It is never stored in plain text.
        return Response({**user_json(user), "temporary_password": password}, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return Response({"detail": "No such user."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data
        try:
            changes = update_user(
                request.user,
                user,
                role=data.get("role"),
                is_active=_yes_no(data.get("is_active")),
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
            )
        except UserAdminError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if changes:
            record(request, AuditEvent.USER_UPDATED, target=user.username, changes=changes)
        return Response(user_json(user))

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return Response({"detail": "No such user."}, status=status.HTTP_404_NOT_FOUND)
        try:
            password = reset_password(request.user, user)
        except UserAdminError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        record(request, AuditEvent.PASSWORD_RESET, target=user.username)
        return Response({**user_json(user), "temporary_password": password})


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # also works while a temporary password must be replaced
def change_password(request):
    """POST /api/auth/change-password/ {current_password, new_password}"""
    try:
        change_own_password(request.user, request.data.get("current_password"), request.data.get("new_password"))
    except UserAdminError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    update_session_auth_hash(request, request.user)  # stay signed in on this device
    record(request, AuditEvent.PASSWORD_CHANGED, target=request.user.username)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "PUT"])
@permission_classes([HasRole, requires("manage_settings")])
def trust_settings(request):
    """GET/PUT /api/settings/trust/  {sources: {code: 0-100}, weights: {field: 0-100}}"""
    if request.method == "PUT":
        try:
            changes = update_trust_settings(request.data.get("sources"), request.data.get("weights"))
        except TrustSettingsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if changes:
            record(request, AuditEvent.SETTINGS_CHANGED, target="trust settings", changes=changes)
    return Response(get_trust_settings())


@api_view(["PUT"])
@permission_classes([HasRole, requires("manage_settings")])
def organization_logo(request):
    """PUT /api/settings/logo/ {logo: "data:image/png;base64,..." or ""}  Sets or removes this organization's logo."""
    try:
        logo = clean_logo(request.data.get("logo"))
    except LogoError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    tenant = request.tenant
    tenant.logo = logo
    tenant.save(update_fields=["logo"])
    record(request, AuditEvent.SETTINGS_CHANGED, target="logo", logo="removed" if not logo else "updated")
    return Response({"logo": logo})
