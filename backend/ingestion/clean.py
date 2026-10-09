"""Turn messy values from source systems into one standard form, so records can be compared.

Every function returns "" (or None for dates) when the value is missing or unusable,
instead of raising. One bad field must not stop a whole sync.
"""

import re
from datetime import date, datetime

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")  # 5 letters, 4 digits, 1 letter, e.g. ABCPK1234F


def clean_mobile(value):
    """'+91 98221 04521' -> '9822104521'. Returns '' if it is not a valid Indian mobile number."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    # Indian mobile numbers have 10 digits and start with 6, 7, 8 or 9.
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return ""


def clean_name(value):
    """'SURESH  KUMAR' -> 'Suresh Kumar'. Mixed-case names are kept as typed ('Rajesh R Iyer')."""
    if not value:
        return ""
    name = " ".join(str(value).split())
    if name.isupper() or name.islower():
        name = name.title()
    return name


def clean_email(value):
    """'NRAO@CLINIC.EXAMPLE' -> 'nrao@clinic.example'. Returns '' if it does not look like an email."""
    if not value:
        return ""
    email = str(value).strip().lower()
    return email if EMAIL_RE.match(email) else ""


def clean_address(value):
    """Collapse repeated spaces and line breaks into single spaces."""
    if not value:
        return ""
    return " ".join(str(value).split())


DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]  # ISO, then Indian day-first formats


def clean_date(value):
    """Accept a date, a datetime, or text like '1984-07-12', '12/07/1984', '12-07-1984'. Returns None if unusable."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def clean_pan(value):
    """' abcpk 1234 f ' -> 'ABCPK1234F'. Returns '' if it is not a valid PAN."""
    if not value:
        return ""
    pan = re.sub(r"\s", "", str(value)).upper()
    return pan if PAN_RE.match(pan) else ""


def clean_aadhaar(value):
    """Keep ONLY the last 4 digits of an Aadhaar number. '1234 5678 9012' -> '9012'.

    Banks may not store full Aadhaar numbers outside a licensed vault, so the rest is dropped here,
    before anything is saved. Already-masked input like 'XXXX XXXX 9012' also works.
    """
    if not value:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return digits[-4:] if len(digits) in (4, 12) else ""


def clean_ckyc(value):
    """CKYC identifiers have 14 digits. Returns '' otherwise."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 14 else ""


GENDERS = {"m": "Male", "male": "Male", "f": "Female", "female": "Female", "o": "Other", "other": "Other",
           "t": "Other", "transgender": "Other"}


def clean_gender(value):
    """'M' / 'male' / 'F' -> 'Male' / 'Female'. Unknown codes become ''."""
    return GENDERS.get(str(value or "").strip().lower(), "")


def clean_text(value):
    """Collapse spaces; used for occupation and income bands."""
    return " ".join(str(value).split()) if value else ""


def clean_record(record):
    """Clean every standard field of one record produced by a connector's to_standard()."""
    return {
        **record,
        "name": clean_name(record.get("name")),
        "father_name": clean_name(record.get("father_name")),
        "dob": clean_date(record.get("dob")),
        "gender": clean_gender(record.get("gender")),
        "pan": clean_pan(record.get("pan")),
        "aadhaar": clean_aadhaar(record.get("aadhaar")),
        "ckyc": clean_ckyc(record.get("ckyc")),
        "mobile": clean_mobile(record.get("mobile")),
        "email": clean_email(record.get("email")),
        "address": clean_address(record.get("address")),
        "perm_address": clean_address(record.get("perm_address")),
        "occupation": clean_text(record.get("occupation")),
        "income": clean_text(record.get("income")),
    }
