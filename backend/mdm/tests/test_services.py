from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from ingestion.models import SourceRecord
from mdm.models import Customer, GoldenField, MatchSuggestion
from mdm.services import build_customers, decide_suggestion
from sources.models import Source


def add_record(source_code, record_id, name, mobile="", email="", dob=None, updated=None):
    return SourceRecord.objects.create(
        source=Source.objects.get(code=source_code),
        source_record_id=record_id,
        name=name,
        mobile=mobile,
        email=email,
        dob=dob,
        source_updated_at=updated,
    )


@pytest.fixture
def suresh(db):
    dob = date(1984, 7, 12)
    add_record("flexcube", "FX1", "Suresh Kumar", "9822104521", "suresh.kumar@mail.example", dob)
    add_record("salesforce", "SF1", "Sooresh Kumar", "9822107788", "skumar84@webmail.example", dob,
               datetime(2026, 2, 14, tzinfo=timezone.utc))
    add_record("branch_csv", "BR1", "Suresh K", "9822107788", "suresh.kumar@mail.example", dob)


def golden(customer, field):
    return GoldenField.objects.get(customer=customer, field=field)


def test_three_records_become_one_customer_with_golden_record(suresh):
    result = build_customers()

    assert (result.records, result.customers, result.created) == (3, 1, 1)
    customer = Customer.objects.get()
    assert golden(customer, "name").value == "Suresh Kumar"  # FLEXCUBE 0.85 beats Salesforce 0.55
    assert golden(customer, "mobile").value == "9822104521"
    assert golden(customer, "mobile").conflicts == 1
    # name, mobile, email, dob from FLEXCUBE (0.85); no address anywhere:
    # 0.25*0.85 + 0.25*0.85 + 0.15*0.85 + 0.15*0.85 = 0.680
    assert customer.trust_score == Decimal("0.680")


def test_rerun_keeps_the_same_customer_id(suresh):
    build_customers()
    first_id = Customer.objects.get().id
    result = build_customers()
    assert result.created == 0
    assert Customer.objects.get().id == first_id


def test_disabling_a_source_changes_the_golden_record_and_score(suresh):
    build_customers()
    Source.objects.filter(code="flexcube").update(enabled=False)
    build_customers()

    customer = Customer.objects.get()
    assert golden(customer, "name").value == "Sooresh Kumar"  # Salesforce now the most trusted left
    assert customer.trust_score < Decimal("0.680")


@pytest.mark.django_db
def test_accepted_suggestion_merges_customers_on_next_run():
    dob = date(1981, 9, 9)
    add_record("flexcube", "FX6", "Nandini V Rao", "9741200765", "nrao@clinic.example", dob)
    add_record("salesforce", "SF5", "Nandhini Rao", "9741255310", "nandini.rao@mail.example", dob)

    result = build_customers()
    assert (result.customers, result.new_suggestions) == (2, 1)

    decide_suggestion(MatchSuggestion.objects.get(), accept=True)
    build_customers()
    assert Customer.objects.count() == 1


@pytest.mark.django_db
def test_pending_suggestion_is_cleared_once_records_are_in_one_customer():
    # Three records that only "probably" match each other: same birth date, similar names.
    dob = date(1990, 3, 5)
    a = add_record("flexcube", "FX2", "Anita Deshmukh", "9890012345", "anita.d@mail.example", dob)
    b = add_record("salesforce", "SF2", "Aneeta Deshmukh", "9890099999", "adeshmukh@office.example", dob)
    c = add_record("branch_csv", "BR2", "Anita S Deshmukh", "9890056712", "", dob)
    build_customers()
    assert MatchSuggestion.objects.filter(status=MatchSuggestion.PENDING).count() == 3

    def suggestion(x, y):
        return MatchSuggestion.objects.get(record_a_id=min(x.id, y.id), record_b_id=max(x.id, y.id))

    decide_suggestion(suggestion(a, b), accept=True)
    build_customers()
    decide_suggestion(suggestion(a, c), accept=True)
    build_customers()

    # All three are one customer now, so the B-C question no longer needs a decision.
    assert Customer.objects.count() == 1
    assert not MatchSuggestion.objects.filter(status=MatchSuggestion.PENDING).exists()
