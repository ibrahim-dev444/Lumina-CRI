from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from audit.models import AuditEvent
from ingestion.models import SourceRecord
from mdm.models import Customer, FieldCorrection, GoldenField, MatchSuggestion
from mdm.services import build_customers, decide_suggestion
from sources.models import Source
from stewardship.services import CorrectionError, decide, propose


def user_in(group, name):
    u = User.objects.create_user(name, password="pass-1234")
    u.groups.add(Group.objects.get(name=group))
    return u


def api_as(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def add_record(code, rid, name, mobile="", email="", dob=None):
    return SourceRecord.objects.create(source=Source.objects.get(code=code), source_record_id=rid,
                                       name=name, mobile=mobile, email=email, dob=dob)


@pytest.fixture
def suresh(db):
    add_record("salesforce", "SF1", "Suresh Kumar", "9822104521", "suresh.kumar@mail.example", date(1984, 7, 12))
    build_customers()
    return Customer.objects.get()


@pytest.fixture
def maker(db):
    return user_in("Relationship manager", "maker")


@pytest.fixture
def checker(db):
    return user_in("Data steward", "checker")


def golden(customer, field):
    return GoldenField.objects.get(customer=customer, field=field)


def test_approved_correction_wins_over_every_source(suresh, maker, checker):
    before = suresh.trust_score
    c = propose(suresh, "mobile", "+91 98221 07788", "KYC form #4471", "Customer changed number", maker)
    assert c.value == "9822107788"  # cleaned like any source value
    assert c.previous_value == "9822104521"
    assert golden(suresh, "mobile").value == "9822104521"  # nothing changes until approved

    decide(c, approve=True, user=checker)

    g = golden(suresh, "mobile")
    assert g.value == "9822107788"
    assert g.trust == Decimal("1.00") and g.correction_id == c.id and g.source_id is None
    suresh.refresh_from_db()
    assert suresh.trust_score > before


def test_nobody_approves_their_own_correction(suresh, checker):
    c = propose(suresh, "email", "suresh@new.example", "Email from customer", "New address", checker)
    with pytest.raises(CorrectionError, match="your own"):
        decide(c, approve=True, user=checker)


def test_rejection_needs_a_reason_and_changes_nothing(suresh, maker, checker):
    c = propose(suresh, "name", "Suresh K Kumar", "PAN card", "Middle initial missing", maker)
    with pytest.raises(CorrectionError, match="why"):
        decide(c, approve=False, user=checker)
    decide(c, approve=False, user=checker, note="PAN card shows no middle initial")
    assert golden(suresh, "name").value == "Suresh Kumar"
    assert FieldCorrection.objects.get().status == "rejected"


@pytest.mark.parametrize(
    "field, value, error",
    [
        ("mobile", "12345", "10-digit"),
        ("email", "not-an-email", "email"),
        ("dob", "31/02/1990", "date of birth"),
        ("mobile", "9822104521", "already the value"),
    ],
)
def test_bad_values_are_refused(suresh, maker, field, value, error):
    with pytest.raises(CorrectionError, match=error):
        propose(suresh, field, value, "ref", "reason", maker)


def test_evidence_and_one_pending_per_field(suresh, maker):
    with pytest.raises(CorrectionError, match="evidence"):
        propose(suresh, "mobile", "9822107788", "", "reason", maker)
    propose(suresh, "mobile", "9822107788", "ref", "reason", maker)
    with pytest.raises(CorrectionError, match="already waiting"):
        propose(suresh, "mobile", "9822100000", "ref", "reason", maker)


def test_api_roles_and_audit(suresh, maker, checker):
    agent = user_in("Contact centre agent", "agent")
    compliance = user_in("Compliance officer", "compliance")
    body = {"field": "mobile", "value": "9822107788", "evidence_ref": "KYC #1", "reason": "New number"}

    assert api_as(agent).post(f"/api/customers/{suresh.id}/corrections/", body).status_code == 403
    response = api_as(maker).post(f"/api/customers/{suresh.id}/corrections/", body)
    assert response.status_code == 201
    cid = response.json()["id"]
    assert response.json()["mine"] is True

    assert api_as(maker).post(f"/api/corrections/{cid}/approve/").status_code == 403  # RM cannot approve
    assert api_as(compliance).post(f"/api/corrections/{cid}/approve/").status_code == 200

    detail = api_as(maker).get(f"/api/customers/{suresh.id}/").json()
    mobile = next(g for g in detail["golden"] if g["field"] == "mobile")
    assert mobile["source_code"] == "correction" and mobile["correction"]["approved_by"] == "compliance"

    actions = set(AuditEvent.objects.values_list("action", flat=True))
    assert {"corr_proposed", "corr_approved", "denied"} <= actions


def test_correction_survives_a_merge(db, maker, checker):
    dob = date(1981, 9, 9)
    add_record("flexcube", "FX6", "Nandini V Rao", "9741200765", "", dob)
    add_record("salesforce", "SF5", "Nandhini Rao", "9741255310", "", dob)
    build_customers()
    sf_customer = Customer.objects.get(links__source_record__source_record_id="SF5")
    c = propose(sf_customer, "email", "nandini@new.example", "Email from customer", "Missing", maker)
    decide(c, approve=True, user=checker)

    decide_suggestion(MatchSuggestion.objects.get(), accept=True)
    build_customers()

    merged = Customer.objects.get()
    assert golden(merged, "email").value == "nandini@new.example"
    assert FieldCorrection.objects.get().customer_id == merged.id
