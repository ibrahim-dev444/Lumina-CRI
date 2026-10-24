from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from audit.models import AuditEvent
from ingestion.models import SourceRecord
from mdm.models import Customer, GoldenField
from mdm.services import build_customers
from sources.models import Source


def client(username, group=None, superuser=False):
    user = User.objects.create_user(username, password="Strong-pass-123", is_superuser=superuser)
    if group:
        user.groups.add(Group.objects.get(name=group))
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def admin(db):
    return client("admin.ft", superuser=True)


@pytest.fixture
def two_systems(db):
    """One customer described by two systems that disagree on the mobile number."""
    core = Source.objects.create(code="core", name="Core banking", category="Core banking", trust="0.80",
                                 connector_type="postgresql",
                                 mapping={"object": "customers", "id_column": "id",
                                          "fields": {"name": "name", "pan": "pan", "mobile": "mobile"}})
    crm = Source.objects.create(code="crm", name="CRM", category="CRM", trust="0.60", connector_type="mysql",
                                mapping={"object": "contacts", "id_column": "id",
                                         "fields": {"name": "name", "mobile": "mobile", "email": "email"}})
    SourceRecord.objects.create(source=core, source_record_id="C1", name="Karan Mehta", pan="ABCDE1234F",
                                mobile="9876501234", email="karan@mail.example", dob=date(1990, 7, 7))
    SourceRecord.objects.create(source=crm, source_record_id="R1", name="Karan Mehta", pan="ABCDE1234F",
                                mobile="9123456780",
                                email="karan@mail.example", dob=date(1990, 7, 7))
    build_customers()
    return core, crm


def test_lists_only_the_fields_the_connector_maps(admin, two_systems):
    body = admin.get("/api/connectors/core/trust/").json()
    assert [f["field"] for f in body["fields"]] == ["name", "pan", "mobile"]
    assert body["default"] == 80 and all(f["trust"] == 80 and not f["own"] for f in body["fields"])


def test_several_fields_get_one_value_and_customers_follow(admin, two_systems):
    customer = Customer.objects.get()
    assert GoldenField.objects.get(customer=customer, field="mobile").value == "9876501234"  # core wins at 80

    saved = admin.put("/api/connectors/crm/trust/", {"trust": {"mobile": 90, "email": 90}}, format="json")
    assert saved.status_code == 200
    by_field = {f["field"]: f for f in saved.json()["fields"]}
    assert by_field["mobile"]["trust"] == 90 and by_field["mobile"]["own"] and by_field["name"]["trust"] == 60

    mobile = GoldenField.objects.get(customer=customer, field="mobile")
    assert mobile.value == "9123456780" and str(mobile.trust) == "0.90"  # the CRM now wins the mobile number
    assert GoldenField.objects.get(customer=customer, field="name").source.code == "core"  # other fields unchanged
    event = AuditEvent.objects.get(action="settings_changed")
    assert event.detail["changes"] == {"mobile": [60, 90], "email": [60, 90]}


def test_score_uses_field_trust(admin, two_systems):
    before = Customer.objects.get().trust_score
    admin.put("/api/connectors/core/trust/", {"trust": {"name": 100, "pan": 100, "mobile": 100}}, format="json")
    assert Customer.objects.get().trust_score > before


def test_unmapped_field_or_bad_value_is_refused(admin, two_systems):
    assert admin.put("/api/connectors/core/trust/", {"trust": {"email": 50}}, format="json").status_code == 400
    for bad in (-1, 101, 55.5, "80", True):
        assert admin.put("/api/connectors/core/trust/", {"trust": {"pan": bad}}, format="json").status_code == 400
    assert admin.put("/api/connectors/core/trust/", {"trust": {}}, format="json").status_code == 400


def test_only_an_administrator_changes_trust(db, two_systems):
    steward = client("steward.ft", "Data steward")
    assert steward.get("/api/connectors/core/trust/").status_code == 200  # everyone can see it
    refused = steward.put("/api/connectors/core/trust/", {"trust": {"pan": 99}}, format="json")
    assert refused.status_code == 403
    assert Source.objects.get(code="core").field_trust == {}


def test_settings_show_how_many_fields_have_their_own_trust(admin, two_systems):
    admin.put("/api/connectors/core/trust/", {"trust": {"pan": 95}}, format="json")
    rows = {s["code"]: s for s in admin.get("/api/settings/trust/").json()["sources"]}
    assert rows["core"]["own_fields"] == 1 and rows["crm"]["own_fields"] == 0
