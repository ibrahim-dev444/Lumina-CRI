"""Which customer fields are sensitive, and how each one is protected and shown.

PAN and CKYC number: stored encrypted, matched by fingerprint, always shown masked. Only compliance
officers and administrators can reveal the full value, with a reason that goes to the audit log.
Aadhaar: only the last 4 digits are ever kept (the full number is dropped as soon as it arrives).
"""

import re

from . import crypto

ENCRYPTED_FIELDS = {"pan", "ckyc"}


def protect(field, plain):
    """Value to store for a cleaned field."""
    return crypto.encrypt(plain) if field in ENCRYPTED_FIELDS else plain


def reveal(field, stored):
    """Plain value of a stored field (decrypts encrypted fields)."""
    return crypto.decrypt(stored) if field in ENCRYPTED_FIELDS else stored


# Titles at the start of a name: never part of who the person is.
NAME_TITLES = re.compile(r"^(?:(?:mr|mrs|ms|miss|dr|shri|sri|smt|kumari|prof|master)\b\.?\s*)+")


def compare_key(field, stored):
    """What to compare when asking 'do these two stored values agree?'."""
    if stored in (None, ""):
        return ""
    if field in ENCRYPTED_FIELDS:
        return crypto.fingerprint(crypto.decrypt(stored))
    text = str(stored).lower()
    if field in ("name", "father_name"):
        text = NAME_TITLES.sub("", text)  # "Mr. Kabir Verma" and "Kabir Verma" are the same name
    return "".join(ch for ch in text if ch.isalnum())


def mask_pan(plain):
    """ABCPK1234F -> XXXXX1234X"""
    return "XXXXX" + plain[5:9] + "X" if plain and len(plain) == 10 else ""


def mask_ckyc(plain):
    """50012345678821 -> XXXXXXXXXX8821"""
    return "X" * (len(plain) - 4) + plain[-4:] if plain and len(plain) > 4 else ""


def mask_aadhaar(last4):
    """1234 -> XXXX XXXX 1234"""
    return f"XXXX XXXX {last4}" if last4 else ""


ALWAYS_MASKED = {"pan": mask_pan, "ckyc": mask_ckyc, "aadhaar": mask_aadhaar}


def display(field, stored):
    """How a stored value appears in the API for everyone (identity numbers always masked)."""
    if stored in (None, ""):
        return stored
    if field in ALWAYS_MASKED:
        return ALWAYS_MASKED[field](reveal(field, stored))
    return stored
