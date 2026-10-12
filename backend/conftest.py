"""Shared test setup."""

import pytest
from django.db import connection
from rest_framework.test import APIClient

from security import crypto

# A throwaway key used only by the test suite. Real keys live in each environment's .env.
TEST_FIELD_KEY = "q2Y0rRk9lW8m2kq3V5yXyvNn3D7m8f8x9oQqY0w1Z2E="

# Tests run inside a test copy of two organizations. Most tests work in "axis"; isolation tests also use "hdfc".
# Using the real codes means connectors and the compliance feed read fake_sources/axis/ like the app does.
TEST_ORGS = [("axis", "Axis Bank"), ("hdfc", "HDFC Bank")]
TEST_ORG = "axis"


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Create the test organizations once per test database (each gets its own schema, fully migrated)."""
    from tenants.models import Domain, Tenant

    with django_db_blocker.unblock():
        Tenant.objects.get_or_create(schema_name="public", defaults={"name": "Lumina platform"})
        for code, name in TEST_ORGS:
            tenant = Tenant.objects.filter(schema_name=code).first() or Tenant.objects.create(
                schema_name=code, name=name
            )
            Domain.objects.get_or_create(domain=code, defaults={"tenant": tenant, "is_primary": True})


@pytest.fixture(autouse=True)
def in_test_organization(request, monkeypatch):
    """Database tests run inside the "axis" schema, and API calls like client.get("/api/customers/") go to
    /t/axis/api/customers/, as the website sends them. Paths that name an organization (/t/...) or belong to
    the shared space (/api/organizations/, /api/health/, /api/platform/) are left as written."""
    uses_db = (
        "db" in request.fixturenames
        or "transactional_db" in request.fixturenames
        or request.node.get_closest_marker("django_db") is not None
    )
    if not uses_db:
        yield
        return
    request.getfixturevalue("db")
    from tenants.models import Tenant

    original = APIClient.generic

    def generic(self, method, path, *args, **kwargs):
        if path.startswith("/api/") and not path.startswith(("/api/organizations/", "/api/health/", "/api/platform/", "/api/internal/")):
            path = f"/t/{TEST_ORG}{path}"
        return original(self, method, path, *args, **kwargs)

    monkeypatch.setattr(APIClient, "generic", generic)
    connection.set_tenant(Tenant.objects.get(schema_name=TEST_ORG))
    yield
    connection.set_schema_to_public()


@pytest.fixture(autouse=True)
def field_encryption_key(settings):
    settings.FIELD_ENCRYPTION_KEY = TEST_FIELD_KEY
    for cached in (crypto._key_material, crypto._fernet, crypto._hash_key):
        cached.cache_clear()
    yield
    for cached in (crypto._key_material, crypto._fernet, crypto._hash_key):
        cached.cache_clear()
