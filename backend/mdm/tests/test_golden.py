from datetime import datetime, timezone
from decimal import Decimal as D

from mdm.golden import pick_winner, trust_score

OLD = datetime(2025, 1, 1, tzinfo=timezone.utc)
NEW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def cand(value, trust, updated_at=None, record_id=1):
    return {"value": value, "trust": D(trust), "updated_at": updated_at, "record_id": record_id, "source_id": 1}


def test_most_trusted_source_wins_even_if_older():
    winner, conflicts = pick_winner([cand("9822104521", "0.85", OLD), cand("9822107788", "0.55", NEW)])
    assert winner["value"] == "9822104521"
    assert conflicts == 1


def test_equal_trust_newest_wins():
    winner, _ = pick_winner([cand("old@mail.example", "0.55", OLD), cand("new@mail.example", "0.55", NEW)])
    assert winner["value"] == "new@mail.example"


def test_empty_values_are_ignored():
    winner, conflicts = pick_winner([cand("", "0.85"), cand(None, "0.85"), cand("a@b.example", "0.40")])
    assert winner["value"] == "a@b.example"
    assert conflicts == 0


def test_same_value_spelled_differently_is_not_a_conflict():
    _, conflicts = pick_winner([cand("Suresh Kumar", "0.85"), cand("suresh  kumar", "0.40")])
    assert conflicts == 0


def test_no_values_at_all():
    assert pick_winner([cand("", "0.85")]) == (None, 0)


WEIGHTS = {"name": D("0.25"), "mobile": D("0.25"), "address": D("0.20"), "email": D("0.15"), "dob": D("0.15")}


def test_trust_score_worked_example_from_the_docs():
    # name and dob from CKYC (1.00), mobile and address from FLEXCUBE (0.85), email from Salesforce (0.55)
    winners = {
        "name": cand("x", "1.00"),
        "mobile": cand("x", "0.85"),
        "address": cand("x", "0.85"),
        "email": cand("x", "0.55"),
        "dob": cand("x", "1.00"),
    }
    assert trust_score(winners, WEIGHTS) == D("0.865")


def test_missing_field_adds_zero():
    winners = {"name": cand("x", "0.85"), "mobile": None, "address": None, "email": None, "dob": None}
    assert trust_score(winners, WEIGHTS) == D("0.213")  # 0.25 x 0.85 = 0.2125, rounded
