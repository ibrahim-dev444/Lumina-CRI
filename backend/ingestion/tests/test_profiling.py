"""Data profiling: checks on the values as sent, the summary per check, and the records behind a check."""

from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from ingestion.profiling import _dob, display_values, profile
from ingestion.sync import ingest_records
from sources.models import Source


@pytest.mark.parametrize("value, title, fmt", [
    ("Mr. Suresh Kumar", "Mr", "Normal"),
    ("MRS ANITA DESHMUKH", "Mrs", "ALL CAPS"),
    ("Smt. Lakshmi  Iyer", "Smt", "Extra spaces"),
    ("A. Sharma", "No title", "Initials"),
    ("Ravi2 Das", "No title", "Contains digits"),
    ("", "Empty", "Empty"),
])
def test_names(value, title, fmt):
    checks = profile({"name": value})
    assert (checks["name.title"], checks["name.format"]) == (title, fmt)


@pytest.mark.parametrize("value, digits, fmt", [
    ("9822104521", "10 digits", "Plain digits"),
    ("982210452", "9 digits", "Plain digits"),
    ("+919822104521", "12 digits", "+91 prefix"),
    ("09822104521", "11 digits", "Leading 0"),
    ("98221-04521", "10 digits", "Spaces or dashes"),
    ("98ABC04521", "Other length", "Contains letters"),
    ("", "Empty", "Empty"),
])
def test_mobiles(value, digits, fmt):
    checks = profile({"mobile": value})
    assert (checks["mobile.digits"], checks["mobile.format"]) == (digits, fmt)


@pytest.mark.parametrize("value, length, fmt", [
    ("ABCPK1234F", "10 characters", "Valid"),
    ("abcpk1234f", "10 characters", "Lowercase"),
    ("ABCPK1234", "9 characters", "Wrong pattern"),
    ("ABCPK 1234F", "10 characters", "Contains spaces"),
    (None, "Empty", "Empty"),
])
def test_pans(value, length, fmt):
    checks = profile({"pan": value})
    assert (checks["pan.length"], checks["pan.format"]) == (length, fmt)


def test_dates_emails_and_gender_codes():
    today = date(2026, 10, 19)
    assert _dob("2031-01-01", today)["dob.check"] == "In the future"
    assert _dob("1915-01-01", today)["dob.check"] == "Over 100 years"
    assert _dob("2012-05-05", today)["dob.check"] == "Under 18"
    assert profile({"email": "asha.mail.example"})["email.format"] == "Missing @"
    assert profile({"email": "asha@"})["email.format"] == "Missing domain"
    assert profile({"gender": "1"})["gender.code"] == "1 / 2"
    assert "pan.length" not in profile({"name": "Asha"})  # unmapped columns are not counted as empty


def test_identity_numbers_are_only_kept_masked():
    shown = display_values({"pan": "ABCPK1234F", "name": "Asha", "mobile": "9822104521"})
    assert shown == {"pan": "XXXXXX234F", "name": "Asha", "mobile": "9822104521"}


@pytest.fixture
def messy(db):
    source = Source.objects.create(code="branch-app", name="Branch app", category="App", trust="0.60",
                                   connector_type="push_api")
    rows = [{"id": f"R{i}", "name": n, "mobile": m, "pan": p} for i, (n, m, p) in enumerate([
        ("Mr. Ravi Das", "982210452", "ABCPK1234F"),
        ("Mrs. Asha Rao", "9822104521", "abcpk1234f"),
        ("Vikram Shetty", "982210453", ""),
    ] + [(f"Mr. Person {i}", "98221045", "ABCPK123") for i in range(12)])]
    ingest_records(source, rows, started_by="test")
    return source


def client_for(group):
    user = User.objects.create_user(f"prof.{group[:4].lower()}", password="Strong-pass-123")
    user.groups.add(Group.objects.get(name=group))
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_summary_counts_and_shares(messy):
    body = client_for("Contact centre agent").get("/api/profiling/?source=branch-app").json()
    assert body["records"] == 15 and body["profiled"] == 15
    checks = {c["key"]: c for c in body["checks"]}
    titles = {v["value"]: v["count"] for v in checks["name.title"]["values"]}
    assert titles == {"Mr": 13, "Mrs": 1, "No title": 1}
    digits = {v["value"]: (v["count"], v["share"]) for v in checks["mobile.digits"]["values"]}
    assert digits["9 digits"] == (2, 13.3) and digits["Other length"] == (12, 80.0)
    assert "email.format" not in checks  # this source does not send email


def test_records_first_ten_then_all_with_combined_checks(messy):
    c = client_for("Relationship manager")
    first = c.get("/api/profiling/records/?source=branch-app&check=name.title:Mr").json()
    assert first["count"] == 13 and len(first["results"]) == 10 and first["page_size"] == 10
    every = c.get("/api/profiling/records/?source=branch-app&check=name.title:Mr&page_size=50").json()
    assert len(every["results"]) == 13
    both = c.get("/api/profiling/records/?check=name.title:Mr&check=mobile.digits:9 digits").json()
    assert both["count"] == 1 and both["results"][0]["values"]["name"] == "Mr. Ravi Das"
    either = c.get("/api/profiling/records/?check=name.title:Mrs&check=name.title:No title").json()
    assert either["count"] == 2


def test_contact_details_masked_for_agents_and_pan_never_shown(messy):
    agent = client_for("Contact centre agent").get("/api/profiling/records/?check=name.title:Mrs").json()
    values = agent["results"][0]["values"]
    assert agent["masked"] and values["mobile"] != "9822104521" and values["pan"].startswith("XXXXXX")
    steward = client_for("Data steward").get("/api/profiling/records/?check=name.title:Mrs").json()
    assert steward["results"][0]["values"]["mobile"] == "9822104521"
    assert APIClient().get("/api/profiling/").status_code == 403
