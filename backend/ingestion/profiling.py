"""Data profiling: how each column's values look as the bank's systems send them, before Lumina cleans them.

Every record gets a set of checks at sync time, for example {"mobile.digits": "9 digits", "name.title": "Mrs"}.
The profiling screen counts records per check value and lists the records behind any of them. Cleaning would
hide these problems (a 9-digit phone simply becomes empty), which is why the raw values are checked.

Identity numbers are checked but never kept: only their check results, and a masked form for display.
"""

import re
from datetime import date

from .clean import clean_date, clean_mobile

# What the screen shows: one card per check, in this order. (key, column label, check label)
CHECKS = [
    ("name.title", "Name", "Title"),
    ("name.format", "Name", "Format"),
    ("mobile.digits", "Mobile", "Number of digits"),
    ("mobile.format", "Mobile", "Format"),
    ("pan.length", "PAN", "Length"),
    ("pan.format", "PAN", "Format"),
    ("email.format", "Email", "Format"),
    ("dob.check", "Date of birth", "Value"),
    ("gender.code", "Gender", "Code used"),
    ("address.check", "Address", "Value"),
    ("father_name.check", "Father's name", "Value"),
    ("occupation.check", "Occupation", "Value"),
    ("income.check", "Income", "Value"),
    ("aadhaar.check", "Aadhaar", "Value"),
    ("ckyc.check", "CKYC number", "Value"),
    ("perm_address.check", "Permanent address", "Value"),
]
LABELS = {key: (column, check) for key, column, check in CHECKS}
EMPTY = "Empty"

TITLES = [("mrs", "Mrs"), ("mr", "Mr"), ("ms", "Ms"), ("miss", "Miss"), ("dr", "Dr"), ("shri", "Shri"),
          ("smt", "Smt"), ("sri", "Shri"), ("kumari", "Kumari")]
PAN_SHAPE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _text(value):
    return "" if value is None else str(value)


def _name(value):
    text = _text(value)
    if not text.strip():
        return {"name.title": EMPTY, "name.format": EMPTY}
    first = re.split(r"[\s.]+", text.strip().lower(), maxsplit=1)[0]
    title = next((label for word, label in TITLES if first == word), "No title")
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if any(ch.isdigit() for ch in text):
        fmt = "Contains digits"
    elif "  " in text or text != text.strip():
        fmt = "Extra spaces"
    elif text.isupper():
        fmt = "ALL CAPS"
    elif text.islower():
        fmt = "all lowercase"
    elif any(len(w.rstrip(".")) == 1 for w in words if w.lower().rstrip(".") not in dict(TITLES)):
        fmt = "Initials"
    elif len(words) == 1 or (title != "No title" and len(words) == 2):
        fmt = "Single word"
    else:
        fmt = "Normal"
    return {"name.title": title, "name.format": fmt}


def _mobile(value):
    text = _text(value).strip()
    if not text:
        return {"mobile.digits": EMPTY, "mobile.format": EMPTY}
    digits = re.sub(r"\D", "", text)
    count = len(digits)
    size = f"{count} digits" if count in (9, 10, 11, 12) else ("No digits" if count == 0 else "Other length")
    if re.search(r"[A-Za-z]", text):
        fmt = "Contains letters"
    elif text.startswith("+91") or (count == 12 and digits.startswith("91")):
        fmt = "+91 prefix"
    elif re.search(r"[\s\-()]", text):
        fmt = "Spaces or dashes"
    elif text.startswith("0"):
        fmt = "Leading 0"
    else:
        fmt = "Plain digits"
    return {"mobile.digits": size, "mobile.format": fmt, "mobile.valid": "Valid" if clean_mobile(text) else "Invalid"}


def _pan(value):
    text = _text(value)
    if not text.strip():
        return {"pan.length": EMPTY, "pan.format": EMPTY}
    compact = re.sub(r"\s", "", text)
    size = f"{len(compact)} characters" if len(compact) in (9, 10, 11) else "Other length"
    if PAN_SHAPE.match(text):
        fmt = "Valid"
    elif " " in text.strip():
        fmt = "Contains spaces"
    elif PAN_SHAPE.match(compact.upper()) and compact != compact.upper():
        fmt = "Lowercase"
    else:
        fmt = "Wrong pattern"
    return {"pan.length": size, "pan.format": fmt}


def _email(value):
    text = _text(value).strip()
    if not text:
        return {"email.format": EMPTY}
    if "@" not in text:
        return {"email.format": "Missing @"}
    if not EMAIL_SHAPE.match(text):
        return {"email.format": "Missing domain"}
    return {"email.format": "UPPERCASE" if text != text.lower() else "Valid"}


def _dob(value, today=None):
    if value in (None, ""):
        return {"dob.check": EMPTY}
    day = clean_date(value)
    if not day:
        return {"dob.check": "Unreadable"}
    today = today or date.today()
    age = today.year - day.year - ((today.month, today.day) < (day.month, day.day))
    if day > today:
        return {"dob.check": "In the future"}
    if age >= 100:
        return {"dob.check": "Over 100 years"}
    if age < 18:
        return {"dob.check": "Under 18"}
    return {"dob.check": "Valid"}


def _gender(value):
    text = _text(value).strip()
    if not text:
        return {"gender.code": EMPTY}
    if text in ("M", "F"):
        return {"gender.code": "M / F"}
    if text in ("Male", "Female"):
        return {"gender.code": "Male / Female"}
    if text in ("1", "2"):
        return {"gender.code": "1 / 2"}
    if text.lower() in ("m", "f", "male", "female"):
        return {"gender.code": "Lowercase"}
    return {"gender.code": "Other"}


def _plain(field, value):
    text = _text(value).strip()
    if not text:
        return {f"{field}.check": EMPTY}
    if field in ("address", "perm_address") and text.isupper() and any(c.isalpha() for c in text):
        return {f"{field}.check": "ALL CAPS"}
    return {f"{field}.check": "Filled"}


def profile(std):
    """Checks for every Lumina field the connector maps. `std` is the record as the system sent it, renamed to
    Lumina's fields but not yet cleaned. Fields the connector does not map are left out (not counted as empty)."""
    result = {}
    makers = {"name": _name, "mobile": _mobile, "pan": _pan, "email": _email, "dob": _dob, "gender": _gender}
    for field, value in std.items():
        if field in makers:
            result.update(makers[field](value))
        elif field in ("address", "perm_address", "father_name", "occupation", "income", "aadhaar", "ckyc"):
            result.update(_plain(field, value))
    return result


def display_values(std):
    """The values as sent, for the profiling list. Identity numbers are reduced to a masked form here, so the
    readable number is never stored; contact details are masked later by role, like everywhere else."""
    out = {}
    for field, value in std.items():
        if field == "source_updated_at" or value in (None, ""):
            continue
        text = _text(value)
        if field in ("pan", "ckyc", "aadhaar"):
            compact = re.sub(r"\s", "", text)
            text = ("X" * max(len(compact) - 4, 0) + compact[-4:]) if len(compact) > 4 else "X" * len(compact)
        out[field] = text[:200]
    return out
