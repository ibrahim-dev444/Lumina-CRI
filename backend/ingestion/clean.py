"""Turn messy values from source systems into one standard form, so records can be compared.

Every function returns "" (or None for dates) when the value is missing or unusable,
instead of raising. One bad field must not stop a whole sync.
"""

import re
from datetime import date, datetime

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


def clean_record(record):
    """Clean every standard field of one record produced by a connector's to_standard()."""
    return {
        **record,
        "name": clean_name(record.get("name")),
        "mobile": clean_mobile(record.get("mobile")),
        "email": clean_email(record.get("email")),
        "address": clean_address(record.get("address")),
        "dob": clean_date(record.get("dob")),
    }
