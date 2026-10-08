"""Decide which source records belong to the same real person.

This file is plain Python with no database code, so it is easy to test and to explain.
Input: a list of records (dicts with id, name, mobile, email, dob).
Output: groups of record ids, one group per person.

How it works:
1. Blocking: only compare two records if they share a mobile, an email or a birth date.
   Comparing every record with every other would be far too slow for millions of rows.
2. Scoring: for each such pair, add points for what agrees.
3. Linking: pairs at or above MATCH_THRESHOLD are the same person. Groups follow chains:
   if A matches B and B matches C, then A, B and C are one person.
4. Review: pairs between REVIEW_THRESHOLD and MATCH_THRESHOLD are probably the same person.
   They are not merged; they are returned as suggestions for a data steward to decide.
   Pairs a steward already accepted are passed in as confirmed_pairs and always linked.
"""

from collections import defaultdict
from itertools import combinations

from rapidfuzz import fuzz

# Points for each kind of agreement. Tuned on our fake data; revisit with the bank on real data.
POINTS_MOBILE = 40
POINTS_EMAIL = 40
POINTS_DOB = 20
POINTS_NAME_MAX = 40  # scaled by how similar the names are

MATCH_THRESHOLD = 70  # at or above: same person, merge automatically
REVIEW_THRESHOLD = 50  # 50 to 69: probably the same person, ask a steward
MIN_NAME_SIMILARITY = 65  # below this, never match: family members share a phone, email or surname


def name_similarity(a, b):
    """0 to 100. Word order is ignored, so 'Kumar Suresh' equals 'Suresh Kumar'."""
    if not a or not b:
        return 0
    return round(fuzz.token_sort_ratio(a.lower(), b.lower()))


def score_pair(a, b):
    """Return (points, reason) for two records."""
    points, reasons = 0, []
    if a["mobile"] and a["mobile"] == b["mobile"]:
        points += POINTS_MOBILE
        reasons.append("same mobile")
    if a["email"] and a["email"] == b["email"]:
        points += POINTS_EMAIL
        reasons.append("same email")
    if a["dob"] and a["dob"] == b["dob"]:
        points += POINTS_DOB
        reasons.append("same dob")
    similarity = name_similarity(a["name"], b["name"])
    points += POINTS_NAME_MAX * similarity / 100
    if similarity < MIN_NAME_SIMILARITY:
        return 0, f"names too different ({similarity}%)"
    return round(points), f"{' + '.join(reasons)}, name {similarity}%"


def candidate_pairs(records):
    """Blocking: pairs of records that share at least one key."""
    buckets = defaultdict(list)
    for r in records:
        for key in ("mobile", "email", "dob"):
            if r[key]:
                buckets[(key, r[key])].append(r["id"])
    pairs = set()
    for ids in buckets.values():
        for x, y in combinations(sorted(ids), 2):
            pairs.add((x, y))
    return sorted(pairs)


def find_groups(records, confirmed_pairs=()):
    """Return (groups, reasons, suggestions).

    groups:      list of sets of record ids, one set per person
    reasons:     {record_id: why it was linked}
    suggestions: list of (id_a, id_b, points, reason) for a steward to review
    """
    by_id = {r["id"]: r for r in records}
    parent = {r["id"]: r["id"] for r in records}  # union-find: each record starts as its own group

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def link(x, y, reason):
        parent[root(y)] = root(x)
        reasons.setdefault(x, reason)
        reasons.setdefault(y, reason)

    reasons, suggestions = {}, []
    for x, y in sorted(confirmed_pairs):
        if x in by_id and y in by_id:
            link(x, y, "confirmed by steward")

    for x, y in candidate_pairs(records):
        points, reason = score_pair(by_id[x], by_id[y])
        if points >= MATCH_THRESHOLD:
            link(x, y, f"{reason} ({points} pts)")
        elif points >= REVIEW_THRESHOLD:
            suggestions.append((x, y, points, reason))

    groups = defaultdict(set)
    for record_id in parent:
        groups[root(record_id)].add(record_id)
    for record_id in parent:
        reasons.setdefault(record_id, "only record")
    # Keep one suggestion per pair of groups (the strongest), and drop it if both records
    # ended up in the same group anyway.
    best = {}
    for s in sorted(suggestions, key=lambda s: -s[2]):
        a, b = root(s[0]), root(s[1])
        if a != b:
            best.setdefault(frozenset((a, b)), s)
    return sorted(groups.values(), key=min), reasons, list(best.values())
