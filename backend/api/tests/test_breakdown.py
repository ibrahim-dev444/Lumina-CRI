from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from ingestion.clean import clean_record
from ingestion.models import SourceRecord
from mdm.services import build_customers
from sources.models import Source


def client_for(group):
    user = User.objects.create_user(f"user.{group[:4].lower()}", password="Strong-pass-123")
    user.groups.add(Group.objects.get(name=group))
    c = APIClient()
    c.force_authenticate(user)
    return c


def add(code, rid, name, email, dob, **values):
    std = clean_record({"name": name, "email": email, "dob": dob, **values})
    std.pop("source_updated_at", None)
    return SourceRecord.objects.create(source=Source.objects.get(code=code), source_record_id=rid, **std)


@pytest.fixture
def people(db):
    add("flexcube", "F1", "Asha Rao", "asha@mail.example", "1990-01-01", gender="F", country="India",
        residency="Resident")
    add("flexcube", "F2", "Ravi Menon", "ravi@mail.example", "1975-05-05", gender="M", country="UAE",
        residency="NRI")
    add("salesforce", "S3", "Daniel Lee", "dan@mail.example", "2005-03-03", gender="M", mobile="+65 91234567")
    add("branch_csv", "B4", "Meera Iyer", "meera@mail.example", "1955-02-02", gender="F")
    build_customers()


def test_breakdown_by_country_and_residency(people):
    c = client_for("Data steward")
    body = c.get("/api/customers/breakdown/", {"by": "country"}).json()
    counts = {g["key"]: g["count"] for g in body["groups"]}
    assert body["total"] == 4 and body["all"] == 4
    assert counts == {"India": 1, "United Arab Emirates": 1, "Singapore": 1, "unknown": 1}
    residency = {g["key"]: g["count"] for g in c.get("/api/customers/breakdown/", {"by": "residency"}).json()["groups"]}
    assert residency == {"Resident": 1, "NRI": 2, "Foreign national": 0, "unknown": 1}  # Singapore guessed NRI


def test_default_is_trust_score_with_fixed_bands(people):
    body = client_for("Data steward").get("/api/customers/breakdown/").json()
    assert body["by"] == "score"
    assert [g["key"] for g in body["groups"]] == ["high", "medium", "low", "none"]
    assert sum(g["count"] for g in body["groups"]) == 4


def test_filters_combine_and_apply_to_the_list(people):
    c = client_for("Data steward")
    body = c.get("/api/customers/breakdown/", {"by": "gender", "residency": "NRI"}).json()
    assert body["total"] == 2 and body["filters"] == {"residency": ["NRI"]}
    assert {g["key"]: g["count"] for g in body["groups"]}["Male"] == 2
    # Same check twice is OR; different checks are AND.
    assert c.get("/api/customers/", {"residency": ["NRI", "Resident"]}).json()["count"] == 3
    assert c.get("/api/customers/", {"residency": "NRI", "country": "Singapore"}).json()["count"] == 1
    assert c.get("/api/customers/", {"source": "branch_csv"}).json()["count"] == 1
    assert c.get("/api/customers/", {"age": "60_plus"}).json()["count"] == 1


def test_age_bands(people):
    groups = client_for("Data steward").get("/api/customers/breakdown/", {"by": "age"}).json()["groups"]
    assert {g["key"]: g["count"] for g in groups} == {"under_25": 1, "25_39": 1, "40_59": 1, "60_plus": 1,
                                                       "unknown": 0}


def test_kyc_risk_is_only_for_compliance_roles(people):
    agent = client_for("Contact centre agent")
    dims = [d["key"] for d in agent.get("/api/customers/breakdown/").json()["dimensions"]]
    assert "risk" not in dims and "kyc" in dims
    assert agent.get("/api/customers/breakdown/", {"by": "risk"}).json()["by"] == "score"
    steward = client_for("Data steward")
    assert "risk" in [d["key"] for d in steward.get("/api/customers/breakdown/").json()["dimensions"]]


def test_counts_only_no_personal_details(people):
    text = client_for("Data steward").get("/api/customers/breakdown/", {"by": "source"}).content.decode()
    assert "Asha" not in text and "asha@" not in text


def test_older_band_links_still_work(people):
    c = client_for("Data steward")
    every = c.get("/api/customers/").json()["count"]
    split = sum(c.get("/api/customers/", {"band": b}).json()["count"] for b in ("high", "medium", "low", "none"))
    assert every == split == 4
