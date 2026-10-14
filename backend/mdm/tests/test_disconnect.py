"""Disconnecting a system hides the customers only it describes, everywhere; reconnecting brings them back
with the same customer ID. Nothing is deleted."""

from datetime import date

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from ingestion.models import SourceRecord
from interactions.models import Interaction
from mdm.models import Customer, MatchSuggestion
from mdm.services import build_customers
from sources.models import Source


def add(code, rid, name, mobile, dob=date(1984, 7, 12)):
    return SourceRecord.objects.create(source=Source.objects.get(code=code), source_record_id=rid, name=name,
                                       mobile=mobile, dob=dob)


@pytest.fixture
def admin(db):
    c = APIClient()
    c.force_authenticate(User.objects.create_user("disc.admin", password="Strong-pass-123", is_superuser=True))
    return c


@pytest.fixture
def people(db):
    only_sf = add("salesforce", "SF1", "Meera Pillai", "9890012345", dob=date(1990, 3, 5))
    both_a = add("flexcube", "FX1", "Suresh Kumar", "9822104521")
    add("salesforce", "SF2", "Suresh Kumar", "9822104521")  # same person in both systems
    add("flexcube", "FX9", "Suresh Kumaar", "9000000009")  # typo: a review pair with SF... only via dob
    build_customers()
    return only_sf.customer_link.customer, both_a.customer_link.customer


def switch(admin, code, on):
    assert admin.patch(f"/api/sources/{code}/", {"enabled": on}, format="json").status_code == 200


def names(admin):
    return sorted(c["name"] for c in admin.get("/api/customers/").json()["results"])


def test_disconnect_hides_only_customers_no_connected_system_describes(admin, people):
    meera, suresh = people
    Interaction.objects.create(customer=meera, channel="call", kind="complaint", summary="Fee charged twice",
                               outcome="escalated", state="open", created_by_name="x")
    assert "Meera Pillai" in names(admin)

    switch(admin, "salesforce", False)
    assert "Meera Pillai" not in names(admin) and "Suresh Kumar" in names(admin)  # still in FLEXCUBE
    hidden = admin.get(f"/api/customers/{meera.id}/")
    assert hidden.status_code == 404 and "disconnected" in hidden.json()["detail"]
    overview = admin.get("/api/overview/").json()
    assert overview["customers"] == Customer.objects.visible().count()
    assert all(c["name"] != "Meera Pillai" for c in overview["scores"])
    assert admin.get("/api/interactions/open/").json() == []  # her complaint waits, hidden
    assert admin.get(f"/api/customers/{meera.id}/briefing/").status_code == 404
    assert not any(s.record_a.source.code == "salesforce" or s.record_b.source.code == "salesforce"
                   for s in MatchSuggestion.objects.visible())

    switch(admin, "salesforce", True)
    back = admin.get(f"/api/customers/{meera.id}/")
    assert back.status_code == 200 and back.json()["name"] == "Meera Pillai"  # same ID, same data
    assert len(admin.get("/api/interactions/open/").json()) == 1
    assert Customer.objects.filter(id=suresh.id).exists()
