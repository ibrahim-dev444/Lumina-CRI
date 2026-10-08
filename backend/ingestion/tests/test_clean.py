from datetime import date, datetime

import pytest

from ingestion.clean import clean_address, clean_date, clean_email, clean_mobile, clean_name


# The messy values below are copied from docker/postgres/init/01-flexcube.sql.
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+91 98221 04521", "9822104521"),
        ("098450-98450", "9845098450"),
        ("+919815567001", "9815567001"),
        ("94470 11882", "9447011882"),
        ("9890012345", "9890012345"),
        ("12345", ""),  # too short
        ("5822104521", ""),  # Indian mobiles never start with 5
        (None, ""),
    ],
)
def test_clean_mobile(raw, expected):
    assert clean_mobile(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("SURESH KUMAR", "Suresh Kumar"),
        ("Anita  Deshmukh", "Anita Deshmukh"),
        ("Rajesh R Iyer", "Rajesh R Iyer"),
        ("  priya chatterjee ", "Priya Chatterjee"),
        ("", ""),
    ],
)
def test_clean_name(raw, expected):
    assert clean_name(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("NRAO@CLINIC.EXAMPLE", "nrao@clinic.example"),
        (" anita.d@mail.example ", "anita.d@mail.example"),
        ("not-an-email", ""),
        (None, ""),
    ],
)
def test_clean_email(raw, expected):
    assert clean_email(raw) == expected


def test_clean_address_collapses_spaces():
    assert clean_address("14 Shanti  Apts.,\n Kothrud") == "14 Shanti Apts., Kothrud"


@pytest.mark.parametrize(
    "raw, expected",
    [
        (date(1984, 7, 12), date(1984, 7, 12)),
        (datetime(1984, 7, 12, 10, 0), date(1984, 7, 12)),
        ("1984-07-12", date(1984, 7, 12)),
        ("12/07/1984", date(1984, 7, 12)),  # Indian day-first format from branch sheets
        ("30-01-1979", date(1979, 1, 30)),
        ("not known", None),
        ("31/02/1990", None),  # no such day
        (None, None),
    ],
)
def test_clean_date(raw, expected):
    assert clean_date(raw) == expected
