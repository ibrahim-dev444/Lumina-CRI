"""Country of residence and residency status (Resident, NRI, Foreign national).

Systems spell countries every way ("UAE", "U.A.E.", "AE", "United Arab Emirates") and code residency their own
way ("R", "NR", "Non-Resident"). These functions turn them into one standard form. When a system does not send
them at all, Lumina guesses from clues it already has: a foreign mobile code, a foreign city in the address, or
an Indian PIN code. Guessed values are marked as guessed, and any value a system actually sends wins over them.
"""

import re

# Standard country names and the other ways systems write them (lower case, dots and extra spaces removed).
COUNTRIES = {
    "India": ["in", "ind", "bharat", "republic of india"],
    "United Arab Emirates": ["ae", "are", "uae", "emirates", "u a e"],
    "United States": ["us", "usa", "united states of america", "america", "u s a", "u s"],
    "United Kingdom": ["gb", "gbr", "uk", "u k", "great britain", "britain", "england"],
    "Singapore": ["sg", "sgp", "republic of singapore"],
    "Canada": ["ca", "can"],
    "Australia": ["au", "aus"],
    "Saudi Arabia": ["sa", "sau", "ksa", "kingdom of saudi arabia"],
    "Qatar": ["qa", "qat"],
    "Oman": ["om", "omn"],
    "Kuwait": ["kw", "kwt"],
    "Bahrain": ["bh", "bhr"],
    "Germany": ["de", "deu", "deutschland"],
    "New Zealand": ["nz", "nzl"],
    "Malaysia": ["my", "mys"],
    "Hong Kong": ["hk", "hkg"],
}
_ALIASES = {name.lower(): name for name in COUNTRIES}
_ALIASES.update({alias: name for name, aliases in COUNTRIES.items() for alias in aliases})
CODES = {alias for aliases in COUNTRIES.values() for alias in aliases if len(alias) <= 3 and " " not in alias}

# International dialling codes Lumina recognises. +1 is shared by the United States and Canada, so it says
# "lives abroad" without naming the country.
DIAL_CODES = {
    "971": "United Arab Emirates", "966": "Saudi Arabia", "974": "Qatar", "968": "Oman", "965": "Kuwait",
    "973": "Bahrain", "852": "Hong Kong", "44": "United Kingdom", "65": "Singapore", "61": "Australia",
    "49": "Germany", "64": "New Zealand", "60": "Malaysia", "1": None,
}

# Places in an address that name the country.
PLACES = {
    "United Arab Emirates": ["dubai", "abu dhabi", "sharjah", "ajman", "uae", "u.a.e"],
    "United States": ["new york", "new jersey", "california", "texas", "seattle", "chicago", "usa", "u.s.a"],
    "United Kingdom": ["london", "manchester", "birmingham", "leicester", "united kingdom"],
    "Singapore": ["singapore"],
    "Canada": ["toronto", "vancouver", "ontario", "brampton", "canada"],
    "Australia": ["sydney", "melbourne", "australia"],
    "Saudi Arabia": ["riyadh", "jeddah", "dammam", "saudi"],
    "Qatar": ["doha", "qatar"],
    "Oman": ["muscat", "oman"],
    "Kuwait": ["kuwait"],
}
INDIAN_PIN = re.compile(r"(?<!\d)[1-9]\d{5}(?!\d)")

RESIDENT, NRI, FOREIGN = "Resident", "NRI", "Foreign national"
RESIDENCY = {
    RESIDENT: ["resident", "r", "res", "ri", "resident indian", "indian resident"],
    NRI: ["nri", "nr", "non resident", "nonresident", "non resident indian", "nro", "nre"],
    FOREIGN: ["foreign national", "foreigner", "foreign", "fn", "oci", "pio", "non indian", "overseas citizen"],
}
_RESIDENCY = {alias: value for value, aliases in RESIDENCY.items() for alias in aliases}


def _key(value):
    return " ".join(re.sub(r"[^a-z ]", " ", str(value).lower()).split())


def clean_country(value):
    """'U.A.E.' / 'AE' / 'united arab emirates' -> 'United Arab Emirates'. An unknown country is kept,
    tidied ('france' -> 'France'); numbers and empty values become ''."""
    if value in (None, ""):
        return ""
    key = _key(value)
    if not key:
        return ""
    if key in _ALIASES:
        return _ALIASES[key]
    joined = key.replace(" ", "")
    if joined in _ALIASES:
        return _ALIASES[joined]
    return key.title()[:60]


def clean_residency(value):
    """'R' / 'Resident Indian' -> 'Resident', 'NR' / 'Non-Resident' -> 'NRI', 'OCI' -> 'Foreign national'."""
    if value in (None, ""):
        return ""
    key = _key(value)
    return _RESIDENCY.get(key) or _RESIDENCY.get(key.replace(" ", ""), "")


def _dial_country(mobile):
    """(True, country or None) when the number carries a foreign dialling code, else (False, None)."""
    text = str(mobile or "").strip()
    if not (text.startswith("+") or text.startswith("00")):
        return False, None
    digits = re.sub(r"\D", "", text)
    digits = digits[2:] if text.startswith("00") else digits
    if digits.startswith("91"):
        return False, None
    for size in (3, 2, 1):
        if digits[:size] in DIAL_CODES:
            return True, DIAL_CODES[digits[:size]]
    return True, None


def _address_country(address):
    text = f" {str(address or '').lower()} "
    for country, places in PLACES.items():
        if any(re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", text) for p in places):
            return country
    return "India" if INDIAN_PIN.search(text) else ""


def place_and_residency(record):
    """Standard country and residency for one record, sent or guessed. Returns (country, residency, guessed)
    where guessed lists the fields Lumina worked out itself."""
    country = clean_country(record.get("country"))
    residency = clean_residency(record.get("residency"))
    guessed = []
    abroad = False
    if not country:
        abroad, country = _dial_country(record.get("mobile"))
        country = country or _address_country(record.get("address"))
        if abroad and country == "India":  # a foreign number beats an Indian PIN in an old address
            country = ""
        if country:
            guessed.append("country")
    if not residency:
        if country == "India":
            residency = RESIDENT
        elif country or abroad:
            residency = NRI
        if residency:
            guessed.append("residency")
    return country, residency, guessed


NRI_ACCOUNT = re.compile(r"(?<![a-z])(nre|nro|fcnr|nri)(?![a-z])", re.I)


def is_nri_account(product_name):
    """NRE, NRO and FCNR accounts, and products named for NRIs, are held only by non-resident Indians."""
    return bool(NRI_ACCOUNT.search(str(product_name or "")))
