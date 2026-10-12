"""The platform console API (/api/platform/...). Runs only in the shared schema, for platform administrators:
logins in the shared schema with is_superuser. Organization staff cannot sign in here, and platform
administrators cannot open an organization's data."""

from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response

from .models import PlatformEvent, Tenant
from .platform import (
    PlatformError,
    create_organization,
    organization_json,
    organizations,
    record_platform_event,
    update_organization,
)


class IsPlatformAdmin(BasePermission):
    message = "Platform administrators only."

    def has_permission(self, request, view):
        in_shared_space = getattr(request, "tenant", None) is not None and request.tenant.schema_name == "public"
        user = request.user
        return bool(in_shared_space and user and user.is_authenticated and user.is_superuser)


def _me(user):
    return {"username": user.username, "name": user.get_full_name() or user.username}


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request):
    return Response({"detail": "CSRF cookie set"})


@api_view(["POST"])
@permission_classes([AllowAny])
def platform_login(request):
    username = str(request.data.get("username", ""))[:150]
    user = authenticate(request, username=username, password=request.data.get("password"))
    if user is None or not user.is_superuser:
        record_platform_event(request, "login_failed", username=username)
        return Response({"detail": "Wrong username or password."}, status=status.HTTP_400_BAD_REQUEST)
    login(request, user)
    record_platform_event(request, "login")
    return Response(_me(user))


@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
def platform_logout(request):
    record_platform_event(request, "logout")
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def platform_me(request):
    return Response(_me(request.user))


@api_view(["GET", "POST"])
@permission_classes([IsPlatformAdmin])
def organization_list(request):
    """GET: every organization with its health card. POST: add one
    {code, name, brand_color, admin_username, admin_first_name, admin_last_name}."""
    if request.method == "GET":
        return Response([organization_json(t) for t in organizations()])
    d = request.data
    try:
        tenant, admin_username, password = create_organization(
            d.get("code"), d.get("name"), d.get("brand_color"),
            d.get("admin_username"), d.get("admin_first_name"), d.get("admin_last_name"),
        )
    except PlatformError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    record_platform_event(request, "org_created", target=tenant.schema_name, name=tenant.name, admin=admin_username)
    # The first administrator's temporary password is shown once; they must replace it at first sign-in.
    return Response(
        {**organization_json(tenant), "admin_username": admin_username, "temporary_password": password},
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH"])
@permission_classes([IsPlatformAdmin])
def organization_detail(request, code):
    """PATCH {name?, brand_color?, status?: "active" | "suspended"}"""
    tenant = Tenant.objects.exclude(schema_name="public").filter(domains__domain=code).first()
    if tenant is None:
        return Response({"detail": "No organization with that code."}, status=status.HTTP_404_NOT_FOUND)
    d = request.data
    try:
        changes = update_organization(tenant, d.get("name"), d.get("brand_color"), d.get("status"))
    except PlatformError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if changes:
        action = {"suspended": "org_suspended", "active": "org_resumed"}.get(d.get("status"), "org_updated")
        record_platform_event(request, action, target=tenant.schema_name, changes=changes)
    return Response(organization_json(tenant))


@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def platform_events(request):
    """The platform team's own activity log, newest first (last 200)."""
    events = PlatformEvent.objects.all()[:200]
    return Response([
        {"id": e.id, "at": e.at.isoformat(), "actor": e.actor_name, "action": e.action, "target": e.target,
         "detail": e.detail}
        for e in events
    ])
