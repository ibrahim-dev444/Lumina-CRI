from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from ingestion.models import SourceRecord
from mdm.models import Customer, MatchSuggestion
from mdm.services import build_customers
from sources.models import Source


def add_record(source_code, record_id, name, mobile="", email="", dob=None):
    return SourceRecord.objects.create(
        source=Source.objects.get(code=source_code), source_record_id=record_id,
        name=name, mobile=mobile, email=email, dob=dob,
    )


@pytest.fixture
def client(db):
    user = User.objects.create_user("steward", password="pass-1234")
    user.groups.add(Group.objects.get(name="Data steward"))
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def data(db):
    dob = date(1984, 7, 12)
    add_record("flexcube", "FX1", "Suresh Kumar", "9822104521", "suresh.kumar@mail.example", dob)
    add_record("branch_csv", "BR1", "Suresh K", "9822107788", "suresh.kumar@mail.example", dob)
    add_record("flexcube", "FX6", "Nandini V Rao", "9741200765", "", date(1981, 9, 9))
    add_record("salesforce", "SF5", "Nandhini Rao", "9741255310", "", date(1981, 9, 9))
    build_customers()


def test_everything_needs_login(db):
    anonymous = APIClient()
    for url in ["/api/sources/", "/api/customers/", "/api/suggestions/", "/api/auth/me/"]:
        assert anonymous.get(url).status_code == 403


def test_login_and_me(db):
    User.objects.create_user("steward", password="pass-1234")
    c = APIClient()
    assert c.post("/api/auth/login/", {"username": "steward", "password": "wrong"}).status_code == 400
    assert c.post("/api/auth/login/", {"username": "steward", "password": "pass-1234"}).status_code == 200
    assert c.get("/api/auth/me/").json()["username"] == "steward"


def test_sources_list(client, data):
    rows = {s["code"]: s for s in client.get("/api/sources/").json()["results"]}
    assert rows["flexcube"]["record_count"] == 2
    assert rows["flexcube"]["trust"] == "0.85"


def test_disabling_a_source_rebuilds_scores(client, data):
    before = Customer.objects.get(links__source_record__source_record_id="FX1").trust_score
    r = client.patch("/api/sources/flexcube/", {"enabled": False}, format="json")
    assert r.status_code == 200
    after = Customer.objects.get(links__source_record__source_record_id="FX1").trust_score
    assert after < before


def test_customer_list_lowest_score_first_and_search(client, data):
    rows = client.get("/api/customers/").json()["results"]
    scores = [float(r["trust_score"]) for r in rows]
    assert scores == sorted(scores)

    found = client.get("/api/customers/", {"search": "suresh"}).json()["results"]
    assert [r["name"] for r in found] == ["Suresh Kumar"]
    assert found[0]["record_count"] == 2

    by_code = client.get("/api/customers/", {"search": found[0]["code"]}).json()["results"]
    assert by_code[0]["id"] == found[0]["id"]


def test_customer_detail_has_golden_record_and_sources(client, data):
    customer_id = client.get("/api/customers/", {"search": "suresh"}).json()["results"][0]["id"]
    body = client.get(f"/api/customers/{customer_id}/").json()
    golden = {g["field"]: g for g in body["golden"]}
    assert golden["mobile"]["value"] == "9822104521"
    assert golden["mobile"]["source_code"] == "flexcube"
    assert golden["mobile"]["conflicts"] == 1
    assert [r["source_code"] for r in body["records"]] == ["flexcube", "branch_csv"]  # most trusted first


def test_accepting_a_suggestion_merges_customers(client, data):
    pending = client.get("/api/suggestions/", {"status": "pending"}).json()["results"]
    assert len(pending) == 1
    assert Customer.objects.count() == 3

    r = client.post(f"/api/suggestions/{pending[0]['id']}/accept/")
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"
    assert Customer.objects.count() == 2
    assert client.post(f"/api/suggestions/{pending[0]['id']}/reject/").status_code == 400
    assert MatchSuggestion.objects.get().status == "accepted"


def test_overview(client, data):
    body = client.get("/api/overview/").json()
    assert body["customers"] == 3
    assert body["source_records"] == 4
    assert body["pending_reviews"] == 1
    assert sum(body["bands"].values()) == 3
    assert sum(b["count"] for b in body["histogram"]) == 3
    assert len(body["lowest_trust"]) == 3


def test_band_filter_and_detail_extras(client, data):
    high = client.get("/api/customers/", {"band": "high"}).json()["results"]
    assert all(r["band"] == "high" for r in high)
    suresh = client.get("/api/customers/", {"search": "suresh"}).json()["results"][0]
    assert suresh["sources"] == ["flexcube", "branch_csv"]
    detail = client.get(f"/api/customers/{suresh['id']}/").json()
    assert detail["weights"]["name"] == "0.25"
