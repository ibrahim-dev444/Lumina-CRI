"""Customer breakdown and the "super filter": every visible customer described by a few facts (trust band, KYC
status, country, residency, KYC risk, source systems, gender, age band), counted by one of them and filtered by
any mix of them. Values of one fact are alternatives (OR); different facts must all hold (AND).

Counts only: no names or numbers leave here. KYC risk is shown only to roles that may see compliance details.
"""

from collections import Counter
from datetime import date

from accounts.roles import can
from compliance.models import KycRecord
from compliance.services import today
from mdm.models import Customer, CustomerLink, GoldenField

UNKNOWN = "unknown"
DIMENSIONS = [
    ("score", "Trust score"), ("kyc", "KYC status"), ("country", "Country"), ("residency", "Residency"),
    ("risk", "KYC risk"), ("source", "Source system"), ("gender", "Gender"), ("age", "Age"),
]
# Fixed order and labels for facts with a known set of values; country and source come from the data.
ORDER = {
    "score": [("high", "High (80+)"), ("medium", "Medium (60-79)"), ("low", "Low (under 60)"), ("none", "No score")],
    "kyc": [("verified", "Verified"), ("due_soon", "Due soon"), ("overdue", "Overdue"), ("no_record", "No KYC record")],
    "residency": [("Resident", "Resident"), ("NRI", "NRI"), ("Foreign national", "Foreign national"),
                  (UNKNOWN, "Not known")],
    "risk": [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("no_record", "No KYC record")],
    "gender": [("Male", "Male"), ("Female", "Female"), ("Other", "Other"), (UNKNOWN, "Not known")],
    "age": [("under_25", "Under 25"), ("25_39", "25 to 39"), ("40_59", "40 to 59"), ("60_plus", "60 and over"),
            (UNKNOWN, "Not known")],
}
TOP_COUNTRIES = 8


def _band(score):
    if score is None:
        return "none"
    return "high" if score >= 0.8 else "medium" if score >= 0.6 else "low"


def _age(dob, on):
    try:
        born = date.fromisoformat(dob)
    except (TypeError, ValueError):
        return UNKNOWN
    years = on.year - born.year - ((on.month, on.day) < (born.month, born.day))
    if years < 0:
        return UNKNOWN
    return "under_25" if years < 25 else "25_39" if years < 40 else "40_59" if years < 60 else "60_plus"


def dimensions_for(user):
    return [(k, label) for k, label in DIMENSIONS if k != "risk" or can(user, "view_compliance")]


def customer_facts():
    """[{id, score, kyc, country, residency, risk, source: {codes}, gender, age}] for every visible customer,
    plus {source code: name}. A handful of queries whatever the number of customers."""
    on = today()
    visible = Customer.objects.visible()
    rows = list(visible.values("id", "trust_score", "pan_hash"))
    golden = {}
    for g in GoldenField.objects.filter(customer__in=visible, field__in=["country", "residency", "gender", "dob"]
                                        ).values("customer_id", "field", "value"):
        golden.setdefault(g["customer_id"], {})[g["field"]] = g["value"]
    sources, names = {}, {}
    links = CustomerLink.objects.filter(customer__in=visible, source_record__active=True,
                                        source_record__source__enabled=True)
    for link in links.values("customer_id", "source_record__source__code", "source_record__source__name"):
        code = link["source_record__source__code"]
        sources.setdefault(link["customer_id"], set()).add(code)
        names[code] = link["source_record__source__name"]
    kyc = {k.pan_hash: k for k in KycRecord.objects.all()}

    facts = []
    for r in rows:
        mine = golden.get(r["id"], {})
        record = kyc.get(r["pan_hash"]) if r["pan_hash"] else None
        facts.append({
            "id": r["id"],
            "score": _band(r["trust_score"]),
            "kyc": record.status(on) if record else "no_record",
            "risk": record.risk if record else "no_record",
            "country": mine.get("country") or UNKNOWN,
            "residency": mine.get("residency") or UNKNOWN,
            "gender": mine.get("gender") or UNKNOWN,
            "age": _age(mine.get("dob"), on),
            "source": sources.get(r["id"], set()),
        })
    return facts, names


def wanted_filters(params, user):
    """{fact: {values}} from ?score=low&country=India&country=Singapore. 'band' is the older name for score."""
    allowed = {k for k, _ in dimensions_for(user)}
    wanted = {}
    for key in allowed:
        values = set(params.getlist(key))
        if key == "score":
            values |= set(params.getlist("band"))
        values.discard("")
        if values:
            wanted[key] = values
    return wanted


def matches(fact, wanted):
    for key, values in wanted.items():
        if key == "source":
            if not fact["source"] & values:
                return False
        elif fact[key] not in values:
            return False
    return True


def _groups(facts, by, names):
    counts = Counter()
    for f in facts:
        if by == "source":
            counts.update(f["source"] or {UNKNOWN})
        else:
            counts[f[by]] += 1
    if by in ORDER:
        return [{"key": k, "label": label, "count": counts.get(k, 0)} for k, label in ORDER[by]]
    if by == "source":
        return sorted(({"key": k, "label": names.get(k, "No source"), "count": n} for k, n in counts.items()),
                      key=lambda g: (-g["count"], g["label"]))
    # Country: the biggest few by name, then everything else together, then customers with no country.
    known = sorted(((k, n) for k, n in counts.items() if k != UNKNOWN), key=lambda kv: (-kv[1], kv[0]))
    groups = [{"key": k, "label": k, "count": n} for k, n in known[:TOP_COUNTRIES]]
    rest = known[TOP_COUNTRIES:]
    if rest:
        groups.append({"key": "__other", "label": f"Other ({len(rest)} countries)", "count": sum(n for _, n in rest),
                       "members": [k for k, _ in rest]})
    if counts.get(UNKNOWN):
        groups.append({"key": UNKNOWN, "label": "Not known", "count": counts[UNKNOWN]})
    return groups


def breakdown(params, user):
    dims = dimensions_for(user)
    by = params.get("by") or "score"
    if by not in {k for k, _ in dims}:
        by = "score"
    facts, names = customer_facts()
    wanted = wanted_filters(params, user)
    chosen = [f for f in facts if matches(f, wanted)]
    total = len(chosen)
    groups = _groups(chosen, by, names)
    for g in groups:
        g["share"] = round(100 * g["count"] / total, 1) if total else 0
    # Every value each fact takes across all customers, for the filter menus (counts before filtering).
    options = {key: [{k: g[k] for k in ("key", "label", "count", "members") if k in g}
                     for g in _groups(facts, key, names) if g["count"]]
               for key, _ in dims}
    return {
        "by": by,
        "total": total,
        "all": len(facts),
        "groups": groups,
        "filters": {k: sorted(v) for k, v in wanted.items()},
        "dimensions": [{"key": k, "label": label} for k, label in dims],
        "options": options,
    }


def filtered_ids(params, user):
    """IDs of the customers the super filter keeps, or None when no filter is set."""
    wanted = wanted_filters(params, user)
    if not wanted:
        return None
    facts, _ = customer_facts()
    return [f["id"] for f in facts if matches(f, wanted)]
