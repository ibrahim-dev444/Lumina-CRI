from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from audit.models import AuditEvent
from compliance.models import ConsentRecord, KycRecord
from compliance.services import ConsentError, current_consents, import_feed, record_consent
from ingestion.models import SourceRecord
from ingestion.sync import _protect_record
from mdm.models import Customer
from mdm.services import build_customers
from security.crypto import fingerprint
from sources.models import Source

PAN = "EHJPS5678K"


def kyc(risk, last_kyc, **extra):
    return KycRecord(pan_hash="x", risk=risk, last_kyc=last_kyc, **extra)


@pytest.mark.parametrize(
    "risk, last_kyc, today, due, status",
    [
        ("high", date(2024, 1, 10), date(2026, 10, 9), date(2026, 1, 10), "overdue"),  # every 2 years
        ("medium", date(2018, 11, 1), date(2026, 10, 9), date(2026, 11, 1), "due_soon"),  # every 8 years
        ("low", date(2022, 8, 19), date(2026, 10, 9), date(2032, 8, 19), "verified"),  # every 10 years
        ("low", date(2016, 2, 29), date(2026, 10, 9), date(2026, 2, 28), "overdue"),  # leap day
    ],
)
def test_re_kyc_due_follows_risk(risk, last_kyc, today, due, status):
    k = kyc(risk, last_kyc)
    assert k.re_kyc_due == due
    assert k.status(today) == status


def add_record(pan, name="Gurpreet Sandhu", source="flexcube"):
    std = _protect_record({"pan": pan, "ckyc": ""})
    return SourceRecord.objects.create(source=Source.objects.get(code=source), source_record_id=pan,
                                       name=name, dob=date(1979, 1, 30), **std)


@pytest.fixture
def gurpreet(db):
    add_record(PAN)
    build_customers()
    KycRecord.objects.create(pan_hash=fingerprint(PAN), risk="high", risk_reason="Cash-intensive business",
                             last_kyc=date(2024, 1, 10), pep=True, pep_note="Related to a PEP",
                             sanctions="potential_match", sanctions_checked=date(2026, 10, 2))
    return Customer.objects.get()


def api_as(group, name):
    user = User.objects.create_user(name, password="pass-1234")
    user.groups.add(Group.objects.get(name=group))
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_customer_is_linked_to_kyc_by_pan_fingerprint(gurpreet):
    assert gurpreet.pan_hash == fingerprint(PAN)


def test_front_line_never_sees_aml_flags(gurpreet):
    for group in ["Contact centre agent", "Relationship manager"]:
        body = api_as(group, group[:5]).get(f"/api/customers/{gurpreet.id}/").json()
        assert body["compliance"]["kyc_status"] == "overdue"  # they may ask for updated documents
        assert body["compliance"]["aml"] is None  # but must not see why the bank watches this customer
        assert "Cash-intensive" not in str(body) and "potential_match" not in str(body)


def test_compliance_sees_aml_flags(gurpreet):
    body = api_as("Compliance officer", "comp").get(f"/api/customers/{gurpreet.id}/").json()
    assert body["compliance"]["aml"]["risk"] == "high"
    assert body["compliance"]["aml"]["pep"] is True


def test_queue_is_compliance_only_and_ordered(gurpreet):
    add_record("ABCPK1234F", "Suresh Kumar")
    build_customers()
    KycRecord.objects.create(pan_hash=fingerprint("ABCPK1234F"), risk="low", last_kyc=date(2025, 1, 1))
    assert api_as("Relationship manager", "rm").get("/api/compliance/").status_code == 403
    body = api_as("Compliance officer", "comp").get("/api/compliance/").json()
    assert [r["risk"] for r in body["results"]] == ["high", "low"]
    assert body["summary"]["overdue"] == 1 and body["summary"]["pep"] == 1
    overdue = api_as("Data steward", "st").get("/api/compliance/", {"status": "overdue"}).json()["results"]
    assert [r["name"] for r in overdue] == ["Gurpreet Sandhu"]


def test_consent_history_is_append_only(db):
    key = fingerprint(PAN)
    record_consent(key, "marketing", "granted", "Branch", "", "rm")
    record_consent(key, "marketing", "revoked", "Call", "Asked us to stop", "agent")
    assert current_consents(key)["marketing"].status == "revoked"
    assert ConsentRecord.objects.filter(pan_hash=key, purpose="marketing").count() == 2  # history kept
    with pytest.raises(ConsentError, match="already revoked"):
        record_consent(key, "marketing", "revoked", "Call", "", "agent")
    with pytest.raises(ConsentError, match="cannot be revoked"):
        record_consent(key, "servicing", "revoked", "Call", "", "agent")
    with pytest.raises(ValueError):
        row = ConsentRecord.objects.first()
        row.note = "edited"
        row.save()


def test_agent_can_record_consent_and_it_is_audited(gurpreet):
    agent = api_as("Contact centre agent", "agent")
    body = {"purpose": "marketing", "status": "revoked", "channel": "Call", "note": "No more offers"}
    assert agent.post(f"/api/customers/{gurpreet.id}/consent/", body).status_code == 201
    assert api_as("Data steward", "st").post(f"/api/customers/{gurpreet.id}/consent/", body).status_code == 403
    event = AuditEvent.objects.get(action="consent")
    assert event.detail["purpose"] == "marketing" and event.detail["status"] == "revoked"


def test_feed_import_links_by_pan_and_is_safe_to_rerun(db):
    kyc_rows, changes = import_feed()
    assert kyc_rows == 10 and changes > 0
    assert KycRecord.objects.filter(pan_hash=fingerprint(PAN), risk="high", pep=True).exists()
    assert not KycRecord.objects.filter(pan_hash=PAN).exists()  # never the readable PAN
    assert import_feed() == (10, 0)  # unchanged consent is not duplicated


def test_compliance_follows_the_customer_through_a_merge(gurpreet):
    add_record(PAN, "Gurprit Singh Sandhu", source="branch_csv")  # same PAN, another system
    build_customers()
    merged = Customer.objects.get()
    body = api_as("Compliance officer", "comp").get(f"/api/customers/{merged.id}/").json()
    assert body["compliance"]["aml"]["risk"] == "high"
