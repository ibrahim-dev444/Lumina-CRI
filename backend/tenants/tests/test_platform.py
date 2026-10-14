"""The platform console: only platform administrators get in, they see counts but never customers, and
suspending an organization closes it to everyone."""

import pytest
from django.contrib.auth.models import Group, User
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from mdm.models import Customer
from tenants.models import PlatformEvent, Tenant


@pytest.fixture
def platform(db):
    with schema_context("public"):
        User.objects.create_user("ops", password="Platform-pass-2026", is_superuser=True, is_staff=True)
    c = APIClient()
    assert c.post("/api/platform/auth/login/", {"username": "ops", "password": "Platform-pass-2026"}).status_code == 200
    return c


def test_bank_logins_cannot_open_the_platform(db):
    User.objects.create_user("axis.admin", password="Strong-pass-123", is_superuser=True)  # axis schema
    c = APIClient()
    assert c.post("/api/platform/auth/login/", {"username": "axis.admin", "password": "Strong-pass-123"}).status_code == 400
    with schema_context("public"):
        User.objects.create_user("plain", password="Strong-pass-123")  # in the shared schema but not an admin
    assert c.post("/api/platform/auth/login/", {"username": "plain", "password": "Strong-pass-123"}).status_code == 400
    assert c.get("/api/platform/organizations/").status_code == 403


def test_signed_in_bank_staff_get_nothing_from_the_platform(db):
    staff = User.objects.create_user("steward.a", password="Strong-pass-123")
    staff.groups.add(Group.objects.get(name="Data steward"))
    c = APIClient()
    c.post("/t/axis/api/auth/login/", {"username": "steward.a", "password": "Strong-pass-123"})
    assert c.get("/api/platform/organizations/").status_code == 403


def test_health_cards_show_counts_not_customers(platform):
    # Test requests switch the connection's schema, so bank data is set up explicitly inside Axis.
    with schema_context("axis"):
        from ingestion.models import SourceRecord
        from mdm.services import build_customers
        from sources.models import Source

        SourceRecord.objects.create(source=Source.objects.get(code="flexcube"), source_record_id="1", name="Asha")
        build_customers()
        Customer.objects.create()  # no connected system describes this one: not counted
    cards = {o["code"]: o for o in platform.get("/api/platform/organizations/").json()}
    assert set(cards) >= {"axis", "hdfc"}
    axis = cards["axis"]["health"]
    assert axis["customers"] == 1 and cards["hdfc"]["health"]["customers"] == 0
    assert set(axis) == {
        "users", "admins", "customers", "source_records", "sources_enabled", "sources_total",
        "last_sync", "pending_reviews", "last_activity",
    }


def test_add_organization_creates_its_own_space_and_first_admin(platform):
    made = platform.post(
        "/api/platform/organizations/",
        {"code": "icici", "name": "ICICI Bank", "brand_color": "#b02a30", "admin_username": "icici.admin",
         "admin_first_name": "First", "admin_last_name": "Admin"},
    )
    assert made.status_code == 201, made.json()
    body = made.json()
    assert body["code"] == "icici" and body["health"]["admins"] == 1 and body["temporary_password"]
    with schema_context("icici"):
        admin = User.objects.get(username="icici.admin")
        assert admin.is_superuser and admin.lumina_profile.must_change_password
        assert admin.check_password(body["temporary_password"])
    with schema_context("axis"):
        assert not User.objects.filter(username="icici.admin").exists()
    assert APIClient().get("/api/organizations/icici/").json()["name"] == "ICICI Bank"
    assert PlatformEvent.objects.filter(action="org_created", target="icici").exists()


@pytest.mark.parametrize("code", ["axis", "public", "platform", "a", "9bank", "Bad Code"])
def test_bad_or_taken_codes_refused(platform, code):
    made = platform.post("/api/platform/organizations/", {"code": code, "name": "Some Bank", "admin_username": "some.admin"})
    assert made.status_code == 400


def test_suspending_closes_the_organization_to_everyone(platform):
    with schema_context("axis"):
        staff = User.objects.create_user("rm.x", password="Strong-pass-123")
        staff.groups.add(Group.objects.get(name="Relationship manager"))
    bank = APIClient()
    bank.post("/t/axis/api/auth/login/", {"username": "rm.x", "password": "Strong-pass-123"})
    assert bank.get("/t/axis/api/customers/").status_code == 200

    assert platform.patch("/api/platform/organizations/axis/", {"status": "suspended"}).json()["status"] == "suspended"
    assert bank.get("/t/axis/api/customers/").status_code == 403  # already signed in, still refused
    assert APIClient().get("/api/organizations/axis/").status_code == 403
    assert PlatformEvent.objects.filter(action="org_suspended", target="axis").exists()

    platform.patch("/api/platform/organizations/axis/", {"status": "active"})
    assert bank.get("/t/axis/api/customers/").status_code == 200
    with schema_context("public"):
        assert Tenant.objects.get(schema_name="axis").status == "active"


def test_rename_and_recolour(platform):
    changed = platform.patch("/api/platform/organizations/hdfc/", {"name": "HDFC Bank Ltd", "brand_color": "#004c8f"})
    assert changed.json()["name"] == "HDFC Bank Ltd"
    assert platform.patch("/api/platform/organizations/hdfc/", {"brand_color": "blue"}).status_code == 400
