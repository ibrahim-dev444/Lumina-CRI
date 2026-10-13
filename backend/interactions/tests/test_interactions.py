"""Conversations and the "Before you speak" briefing."""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group, User
from django.utils import timezone
from rest_framework.test import APIClient

from audit.models import AuditEvent
from compliance.models import ConsentRecord, KycRecord
from ingestion.models import SourceRecord
from ingestion.sync import _protect_record
from interactions.models import Interaction
from interactions.services import mask_numbers
from mdm.models import Customer, MatchSuggestion
from mdm.services import build_customers, decide_suggestion
from products.models import Holding
from security.crypto import fingerprint
from sources.models import Source

PAN = "ABCPK1234F"


def add_record(code, rid, name, pan="", mobile="", dob=date(1984, 7, 12)):
    std = _protect_record({"pan": pan, "ckyc": ""})
    return SourceRecord.objects.create(source=Source.objects.get(code=code), source_record_id=rid, name=name,
                                       mobile=mobile, dob=dob, **std)


def api_as(group):
    user = User.objects.create_user(f"{group[:5].lower()}.{User.objects.count()}", password="pass-1234")
    user.groups.add(Group.objects.get(name=group))
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def suresh(db):
    add_record("flexcube", "FX1", "Suresh Kumar", pan=PAN, mobile="9822104521")
    build_customers()
    return Customer.objects.get()


def log(client, customer, **body):
    data = {"channel": "call", "kind": "query", "summary": "Asked about the card statement.", "outcome": "resolved",
            **body}
    return client.post(f"/api/customers/{customer.id}/interactions/", data, format="json")


@pytest.mark.parametrize("text, expected", [
    ("Card 4111 1111 1111 1234 was blocked", "Card XXXX1234 was blocked"),
    ("account 912010045671234 debited", "account XXXX1234 debited"),
    ("PAN abcpk1234f given", "PAN [PAN hidden] given"),
    ("Aadhaar 2345 6789 0123 shown", "Aadhaar XXXX0123 shown"),
    ("Call back on 9822104521 after 5", "Call back on 9822104521 after 5"),  # a phone number stays
])
def test_numbers_are_masked(text, expected):
    assert mask_numbers(text) == expected


def test_logging_masks_numbers_and_audits_without_the_note(suresh):
    made = log(api_as("Contact centre agent"), suresh, summary="Customer read out card 4111111111111234 by mistake.")
    assert made.status_code == 201, made.json()
    assert made.json()["summary"] == "Customer read out card XXXX1234 by mistake."
    assert made.json()["state"] == "closed"
    event = AuditEvent.objects.get(action="interaction")
    assert event.target == suresh.code and "summary" not in event.detail


def test_complaints_and_follow_ups_stay_open_until_closed(suresh):
    agent = api_as("Contact centre agent")
    complaint = log(agent, suresh, kind="complaint", outcome="escalated", summary="Charged twice for the annual fee.")
    assert complaint.json()["state"] == "open"
    assert log(agent, suresh, outcome="follow_up").status_code == 400  # needs a date
    soon = (timezone.localdate() + timedelta(days=2)).isoformat()
    assert log(agent, suresh, outcome="follow_up", follow_up_on=soon).json()["state"] == "open"
    assert len(agent.get("/api/interactions/open/").json()) == 2

    cid = complaint.json()["id"]
    assert agent.post(f"/api/interactions/{cid}/close/", {"note": "ok"}, format="json").status_code == 400
    closed = agent.post(f"/api/interactions/{cid}/close/", {"note": "Fee reversed on 14 Oct."}, format="json")
    assert closed.json()["state"] == "closed" and closed.json()["closed_by"].startswith("conta")
    assert agent.post(f"/api/interactions/{cid}/close/", {"note": "again please"}, format="json").status_code == 400


def test_bad_input_is_refused(suresh):
    agent = api_as("Contact centre agent")
    assert log(agent, suresh, channel="pigeon").status_code == 400
    assert log(agent, suresh, summary="hi").status_code == 400
    past = (timezone.localdate() - timedelta(days=1)).isoformat()
    assert log(agent, suresh, outcome="follow_up", follow_up_on=past).status_code == 400
    assert APIClient().get(f"/api/customers/{suresh.id}/briefing/").status_code == 403


def test_conversations_follow_a_merge(db):
    a = add_record("flexcube", "FX1", "Suresh Kumar", mobile="9822104521")
    add_record("salesforce", "SF1", "Suresh Kumaar", mobile="9000000009")  # same dob, typo: review, not merge
    build_customers()
    first = a.customer_link.customer
    log(api_as("Contact centre agent"), first)
    other = Customer.objects.exclude(id=first.id).get()
    log(api_as("Relationship manager"), other, summary="Met at the branch about a home loan.")
    decide_suggestion(MatchSuggestion.objects.get(), accept=True)
    build_customers()
    survivor = Customer.objects.get()
    assert survivor.interactions.count() == 2


def test_briefing_puts_problems_first_and_hides_amounts_and_aml_by_role(suresh):
    record = SourceRecord.objects.get()
    Holding.objects.create(source=record.source, account_key="k1", account_last4="1234", customer_ref="FX1",
                           product_type="credit_card", product_name="Platinum Card", status="overdue",
                           balance=22400)
    Holding.objects.create(source=record.source, account_key="k2", account_last4="5678", customer_ref="FX1",
                           product_type="savings", product_name="Prime Savings", status="active", balance=120000,
                           opened_on=date(2013, 2, 8))
    KycRecord.objects.create(pan_hash=fingerprint(PAN), risk="high", last_kyc=date(2015, 1, 1), pep=True)
    ConsentRecord.objects.create(pan_hash=fingerprint(PAN), purpose="marketing", status="revoked",
                                 channel="Branch", recorded_by_name="x")
    agent = api_as("Contact centre agent")
    log(agent, suresh, kind="complaint", outcome="escalated", summary="Card blocked while travelling abroad.")

    brief = agent.get(f"/api/customers/{suresh.id}/briefing/").json()
    kinds = [a["kind"] for a in brief["alerts"]]
    assert brief["alerts"][0]["level"] == "bad" and {"complaint", "overdue", "kyc", "consent"} <= set(kinds)
    assert "compliance" not in kinds  # never shown to front-line staff
    assert "₹22,400" in next(a["title"] for a in brief["alerts"] if a["kind"] == "overdue")
    assert brief["open_items"] == 1 and brief["last_contact"]["channel"] == "Phone call"
    assert "Holds Prime Savings since 2013." in brief["talking_points"]
    assert brief["headline"].endswith("to handle first")

    steward = api_as("Data steward").get(f"/api/customers/{suresh.id}/briefing/").json()
    assert "₹" not in next(a["title"] for a in steward["alerts"] if a["kind"] == "overdue")  # no amounts
    compliance = next(a for a in steward["alerts"] if a["kind"] == "compliance")
    assert "politically exposed" in compliance["title"] and "Never mention" in compliance["action"]


def test_quiet_customer_gets_a_calm_briefing(suresh):
    brief = api_as("Relationship manager").get(f"/api/customers/{suresh.id}/briefing/").json()
    assert brief["alerts"] == [] and brief["headline"] == "Nothing to flag. Good to talk."
    assert brief["last_contact"] is None and Interaction.objects.count() == 0
