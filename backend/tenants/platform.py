"""The platform team's work: add organizations, change or suspend them, and see how each one is doing.

The platform team never sees inside an organization. organization_health() returns counts and dates only
(how many users, customers, sources), never a customer's name or details.
"""

import re

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max
from django_tenants.utils import schema_context

from .models import Domain, PlatformEvent, Tenant

CODE = re.compile(r"^[a-z][a-z0-9]{1,19}$")
RESERVED_CODES = {"public", "platform", "api", "admin", "static", "assets", "signin", "lumina", "www", "t"}
COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


class PlatformError(ValueError):
    pass


def record_platform_event(request, action, target="", **detail):
    user = getattr(request, "user", None)
    signed_in = user is not None and user.is_authenticated
    return PlatformEvent.objects.create(
        actor_name=user.get_username() if signed_in else str(detail.pop("username", "") or "anonymous"),
        action=action,
        target=target,
        detail=detail,
        ip=request.META.get("REMOTE_ADDR") or None,
    )


def organizations():
    return Tenant.objects.exclude(schema_name="public").order_by("name")


def organization_health(tenant):
    """Counts and dates for one organization's health card. Nothing that identifies a customer."""
    from audit.models import AuditEvent
    from ingestion.models import SourceRecord
    from mdm.models import Customer, MatchSuggestion
    from sources.models import Source

    with schema_context(tenant.schema_name):
        sources = Source.objects.all()
        return {
            "users": User.objects.filter(is_active=True).count(),
            "admins": User.objects.filter(is_active=True, is_superuser=True).count(),
            "customers": Customer.objects.visible().count(),
            "source_records": SourceRecord.objects.filter(source__enabled=True, active=True).count(),
            "sources_enabled": sources.filter(enabled=True).count(),
            "sources_total": sources.count(),
            "last_sync": _iso(sources.aggregate(m=Max("last_synced_at"))["m"]),
            "pending_reviews": MatchSuggestion.objects.visible().filter(status=MatchSuggestion.PENDING).count(),
            "last_activity": _iso(AuditEvent.objects.aggregate(m=Max("at"))["m"]),
        }


def _iso(value):
    return value.isoformat() if value else None


def organization_json(tenant, health=True):
    domain = tenant.domains.filter(is_primary=True).first() or tenant.domains.first()
    data = {
        "code": domain.domain if domain else tenant.schema_name,
        "name": tenant.name,
        "status": tenant.status,
        "brand_color": tenant.brand_color,
        "logo": tenant.logo if tenant.logo.startswith(("https://", "data:image/")) else "",
        "created_at": tenant.created_at.isoformat(),
    }
    if health:
        data["health"] = organization_health(tenant)
    return data


def _clean_name(name):
    name = (name or "").strip()
    if not 2 <= len(name) <= 120:
        raise PlatformError("Name: 2 to 120 characters, for example Axis Bank.")
    return name


def _clean_colour(colour):
    colour = (colour or "").strip()
    if colour and not COLOUR.match(colour):
        raise PlatformError("Colour must look like #97144d.")
    return colour


def create_organization(code, name, brand_color, admin_username, admin_first_name, admin_last_name):
    """Create the organization's own schema (with every table), its address code and its first administrator.
    Returns (tenant, admin_username, temporary_password). The password is shown once to the platform team."""
    from accounts.models import AccountProfile
    from accounts.services import USERNAME, temporary_password

    code = (code or "").strip().lower()
    if not CODE.match(code) or code in RESERVED_CODES:
        raise PlatformError("Code: 2 to 20 lowercase letters or numbers, starting with a letter, e.g. icici.")
    if Tenant.objects.filter(schema_name=code).exists() or Domain.objects.filter(domain=code).exists():
        raise PlatformError(f"The code {code} is already used.")
    name = _clean_name(name)
    brand_color = _clean_colour(brand_color)
    admin_username = (admin_username or "").strip().lower()
    if not USERNAME.match(admin_username):
        raise PlatformError("Admin username: 3 to 40 lowercase letters, numbers, dots, dashes or underscores.")

    # Creating the tenant creates its PostgreSQL schema and runs every migration in it (a few seconds).
    tenant = Tenant.objects.create(schema_name=code, name=name, brand_color=brand_color)
    Domain.objects.create(domain=code, tenant=tenant, is_primary=True)

    password = temporary_password()
    with schema_context(code), transaction.atomic():
        admin = User.objects.create_user(
            admin_username,
            password=password,
            first_name=(admin_first_name or "").strip()[:150],
            last_name=(admin_last_name or "").strip()[:150],
            is_staff=True,
            is_superuser=True,
        )
        AccountProfile.objects.create(user=admin, must_change_password=True, created_by="platform")
        if not settings.DEMO_SOURCES:
            from ingestion.retire import remove_demo_sources

            remove_demo_sources()  # the migrations add the built-in demo sources to every new organization
    return tenant, admin_username, password


def update_organization(tenant, name=None, brand_color=None, status=None):
    """Change name, colour or status (active / suspended). Returns {field: [old, new]} for the activity log."""
    changes = {}
    if name is not None and _clean_name(name) != tenant.name:
        changes["name"] = [tenant.name, _clean_name(name)]
        tenant.name = _clean_name(name)
    if brand_color is not None and _clean_colour(brand_color) != tenant.brand_color:
        changes["brand_color"] = [tenant.brand_color, _clean_colour(brand_color)]
        tenant.brand_color = _clean_colour(brand_color)
    if status is not None and status != tenant.status:
        if status not in (Tenant.ACTIVE, Tenant.SUSPENDED):
            raise PlatformError("Status must be active or suspended.")
        changes["status"] = [tenant.status, status]
        tenant.status = status
    if changes:
        tenant.save(update_fields=["name", "brand_color", "status"])
    return changes
