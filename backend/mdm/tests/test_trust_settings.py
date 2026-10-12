from datetime import date

import pytest
from django.contrib.auth.models import User
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from audit.models import AuditEvent
from ingestion.models import SourceRecord
from mdm.models import Customer, FieldWeight
from mdm.services import build_customers
from sources.models import Source


@pytest.fixture
def admin(db):
    c = APIClient()
    c.force_authenticate(User.objects.create_user("admin.t", password="Strong-pass-123", is_superuser=True))
    return c


@pytest.fixture
def one_customer(db):
    SourceRecord.objects.create(
        source=Source.objects.get(code="salesforce"), source_record_id="SF1", name="Karan Mehta",
        mobile="9876501234", email="karan.mehta@mail.example", dob=date(1990, 7, 7),
    )
    build_customers()
    return Customer.objects.get()


def test_settings_are_shown_as_whole_numbers(admin):
    body = admin.get("/api/settings/trust/").json()
    trust = {s["code"]: s["trust"] for s in body["sources"]}
    assert trust == {"flexcube": 85, "salesforce": 55, "branch_csv": 40}
    assert sum(w["points"] for w in body["weights"]) == 100 and len(body["weights"]) == 13


def test_changing_source_trust_rescores_customers(admin, one_customer):
    before = one_customer.trust_score
    saved = admin.put("/api/settings/trust/", {"sources": {"salesforce": 70}}, format="json")
    assert saved.status_code == 200
    one_customer.refresh_from_db()
    assert one_customer.trust_score > before
    event = AuditEvent.objects.get(action="settings_changed")
    assert event.detail["changes"]["source salesforce"] == [55, 70]


def test_field_points_must_add_up_to_100(admin):
    bad = admin.put("/api/settings/trust/", {"weights": {"income": 20}}, format="json")
    assert bad.status_code == 400 and "add up to 100" in bad.json()["detail"]
    ok = admin.put("/api/settings/trust/", {"weights": {"income": 6, "occupation": 0, "gender": 0}}, format="json")
    assert ok.status_code == 200
    assert str(FieldWeight.objects.get(field="income").weight) == "0.06"


@pytest.mark.parametrize("value", [-1, 101, 55.5, "80", True])
def test_trust_must_be_whole_number_0_to_100(admin, value):
    assert admin.put("/api/settings/trust/", {"sources": {"flexcube": value}}, format="json").status_code == 400


def test_each_bank_keeps_its_own_settings(admin):
    admin.put("/api/settings/trust/", {"sources": {"flexcube": 95}}, format="json")
    with schema_context("hdfc"):
        assert str(Source.objects.get(code="flexcube").trust) == "0.85"
