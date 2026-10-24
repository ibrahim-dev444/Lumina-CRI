from datetime import date

import pytest

from ingestion.clean import clean_record
from ingestion.models import SourceRecord
from ingestion.places import clean_country, clean_residency, is_nri_account, place_and_residency
from ingestion.profiling import profile
from mdm.models import Customer, GoldenField
from mdm.services import build_customers
from products.models import Holding
from sources.models import Source


@pytest.mark.parametrize("sent, standard", [
    ("UAE", "United Arab Emirates"), ("U.A.E.", "United Arab Emirates"), ("ae", "United Arab Emirates"),
    ("united arab emirates", "United Arab Emirates"), ("USA", "United States"), ("U.S.A", "United States"),
    ("UK", "United Kingdom"), ("IN", "India"), ("india", "India"), ("SGP", "Singapore"),
    ("france", "France"), ("", ""), (None, ""), ("1234", ""),
])
def test_country_spellings_become_one_name(sent, standard):
    assert clean_country(sent) == standard


@pytest.mark.parametrize("sent, standard", [
    ("R", "Resident"), ("Resident Indian", "Resident"), ("NRI", "NRI"), ("Non-Resident", "NRI"), ("NR", "NRI"),
    ("OCI", "Foreign national"), ("Foreigner", "Foreign national"), ("xyz", ""), ("", ""),
])
def test_residency_codes_become_one_word(sent, standard):
    assert clean_residency(sent) == standard


def test_sent_values_are_used_and_not_marked_guessed():
    assert place_and_residency({"country": "UAE", "residency": "NR"}) == ("United Arab Emirates", "NRI", [])


def test_country_sent_without_residency():
    assert place_and_residency({"country": "India"}) == ("India", "Resident", ["residency"])
    assert place_and_residency({"country": "Canada"}) == ("Canada", "NRI", ["residency"])


@pytest.mark.parametrize("record, expected", [
    ({"mobile": "+971 50 123 4567"}, ("United Arab Emirates", "NRI", ["country", "residency"])),
    ({"mobile": "+1 415 555 0101"}, ("", "NRI", ["residency"])),  # US or Canada: abroad, country unknown
    ({"address": "Flat 1203, Marina Heights, Dubai Marina, Dubai"}, ("United Arab Emirates", "NRI", ["country", "residency"])),
    ({"address": "12, Koramangala, Bengaluru 560034"}, ("India", "Resident", ["country", "residency"])),
    ({"mobile": "+91 98221 04521", "address": "no pin"}, ("", "", [])),
    ({"mobile": "+44 7700 900123", "address": "12, Aundh, Pune 411007"}, ("United Kingdom", "NRI", ["country", "residency"])),
])
def test_guesses_from_mobile_and_address(record, expected):
    assert place_and_residency(record) == expected


def test_clean_record_carries_country_residency_and_guesses():
    out = clean_record({"name": "Ravi Shah", "mobile": "+971501234567", "residency": "Non Resident"})
    assert (out["country"], out["residency"], out["guessed"]) == ("United Arab Emirates", "NRI", ["country"])


def test_nri_account_names():
    assert is_nri_account("NRE Savings Account") and is_nri_account("fcnr deposit") and is_nri_account("NRO-SB")
    assert is_nri_account("NRI Home Loan")
    assert not is_nri_account("Prime Savings Account") and not is_nri_account("Generic")


def test_profiling_country_and_residency():
    checks = profile({"country": "united arab emirates", "residency": "NRI"})
    assert checks == {"country.check": "Other spelling", "residency.code": "Resident / NRI / Foreign national"}
    assert profile({"country": "AE"})["country.check"] == profile({"country": "U.A.E"})["country.check"] == "Short code"
    assert profile({"country": "India"})["country.check"] == "Full name"
    assert profile({"country": "Atlantis"})["country.check"] == "Unknown"
    assert profile({"residency": "NR"})["residency.code"] == "Other code"
    assert profile({"residency": ""})["residency.code"] == "Empty"


@pytest.fixture
def core(db):
    return Source.objects.create(code="core-x", name="Core", category="Core banking", trust="0.80",
                                 connector_type="postgresql")


def _record(source, rid, **values):
    std = clean_record({"name": "Meera Iyer", "dob": "1988-02-03", "email": "meera@mail.example", **values})
    std.pop("source_updated_at", None)
    return SourceRecord.objects.create(source=source, source_record_id=rid, **std)


def test_sent_value_beats_a_guess_whatever_the_trust(core):
    app = Source.objects.create(code="app-x", name="App", category="App", trust="0.40", connector_type="push_api")
    _record(core, "C1", address="12, Adyar, Chennai 600020")  # guessed India / Resident, trust 0.80
    _record(app, "A1", country="UAE", residency="NRI")  # sent, trust only 0.40
    build_customers()
    golden = {g.field: g for g in GoldenField.objects.filter(customer=Customer.objects.get())}
    assert golden["country"].value == "United Arab Emirates" and not golden["country"].guessed
    assert golden["residency"].value == "NRI" and golden["residency"].source.code == "app-x"


def test_guessed_value_is_kept_and_marked(core):
    _record(core, "C1", mobile="+44 7700 900123")
    build_customers()
    golden = {g.field: g for g in GoldenField.objects.filter(customer=Customer.objects.get())}
    assert golden["country"].value == "United Kingdom" and golden["country"].guessed
    assert str(golden["country"].trust) == "0.30"


def test_nre_account_makes_a_guessed_resident_an_nri(core):
    _record(core, "C1", address="12, Adyar, Chennai 600020")  # Indian PIN: guessed Resident
    Holding.objects.create(source=core, account_key="k1", customer_ref="C1", product_type="savings",
                           product_name="NRE Savings Account", opened_on=date(2020, 1, 1))
    build_customers()
    residency = GoldenField.objects.get(customer=Customer.objects.get(), field="residency")
    assert residency.value == "NRI" and residency.guessed


def test_nre_account_never_overrides_a_sent_residency(core):
    _record(core, "C1", residency="Resident")
    Holding.objects.create(source=core, account_key="k1", customer_ref="C1", product_type="savings",
                           product_name="NRO Savings", opened_on=date(2020, 1, 1))
    build_customers()
    residency = GoldenField.objects.get(customer=Customer.objects.get(), field="residency")
    assert residency.value == "Resident" and not residency.guessed


def test_corrections_clean_country_and_residency():
    from stewardship.services import CorrectionError, _clean_value

    assert _clean_value("country", "u.a.e") == "United Arab Emirates"
    assert _clean_value("residency", "non resident") == "NRI"
    with pytest.raises(CorrectionError):
        _clean_value("residency", "maybe")
