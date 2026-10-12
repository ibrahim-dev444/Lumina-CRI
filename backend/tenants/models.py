from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Tenant(TenantMixin):
    """One organization that uses Lumina, e.g. Axis Bank.

    Each tenant has its own PostgreSQL schema (schema_name) holding all of its customers, users, connectors
    and audit log. Code running for one tenant cannot read another tenant's tables. This row itself lives in
    the shared "public" schema, which only the platform team (super admin) works in.
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    STATUS_CHOICES = [(ACTIVE, "Active"), (SUSPENDED, "Suspended")]

    name = models.CharField(max_length=120)  # shown to people: "Axis Bank"
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=ACTIVE)
    brand_color = models.CharField(max_length=7, blank=True)  # e.g. "#97144d"; empty uses Lumina's colour
    created_at = models.DateTimeField(auto_now_add=True)

    # Saving a new tenant creates its schema and runs every tenant migration in it.
    auto_create_schema = True

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    """How requests find their tenant. With subfolder routing this is the short organization code people
    type at sign-in ("axis"), used in addresses like /t/axis/."""
