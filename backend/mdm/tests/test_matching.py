from datetime import date

from mdm.matching import find_groups, name_similarity, score_pair


def rec(id, name, mobile="", email="", dob=None):
    return {"id": id, "name": name, "mobile": mobile, "email": email, "dob": dob}


DOB = date(1984, 7, 12)
SURESH_FX = rec(1, "Suresh Kumar", "9822104521", "suresh.kumar@mail.example", DOB)
SURESH_SF = rec(2, "Sooresh Kumar", "9822107788", "skumar84@webmail.example", DOB)
SURESH_CSV = rec(3, "Suresh K", "9822107788", "suresh.kumar@mail.example", DOB)


def test_name_similarity_ignores_word_order_and_case():
    assert name_similarity("Kumar Suresh", "SURESH KUMAR") == 100
    assert name_similarity("Suresh Kumar", "") == 0


def test_same_email_and_dob_is_a_strong_match():
    points, reason = score_pair(SURESH_FX, SURESH_CSV)
    assert points >= 70
    assert "same email" in reason


def test_shared_phone_with_a_different_name_never_matches():
    # e.g. a husband and wife who give the same family mobile number
    wife = rec(9, "Meena Kumar", "9822104521", "", date(1987, 1, 5))
    points, reason = score_pair(SURESH_FX, wife)
    assert points == 0
    assert "names too different" in reason


def test_chain_links_three_records_into_one_customer():
    # FX and SF share nothing strong, but both match CSV, so all three are one person.
    groups, reasons, _ = find_groups([SURESH_FX, SURESH_SF, SURESH_CSV])
    assert groups == [{1, 2, 3}]
    assert reasons[1] != "only record"


def test_same_dob_and_similar_name_only_is_a_suggestion_not_a_merge():
    a = rec(1, "Nandini V Rao", "9741200765", "nrao@clinic.example", date(1981, 9, 9))
    b = rec(2, "Nandhini Rao", "9741255310", "nandini.rao@mail.example", date(1981, 9, 9))
    groups, _, suggestions = find_groups([a, b])
    assert groups == [{1}, {2}]
    assert [(s[0], s[1]) for s in suggestions] == [(1, 2)]


def test_confirmed_pair_is_merged():
    a = rec(1, "Nandini V Rao", dob=date(1981, 9, 9))
    b = rec(2, "Nandhini Rao", dob=date(1981, 9, 9))
    groups, reasons, suggestions = find_groups([a, b], confirmed_pairs={(1, 2)})
    assert groups == [{1, 2}]
    assert reasons[1] == "confirmed by steward"
    assert suggestions == []


def test_records_with_no_shared_key_are_never_compared():
    groups, _, suggestions = find_groups([rec(1, "Arjun Menon", "9876543210"), rec(2, "Arjun Menon", "9000000001")])
    assert groups == [{1}, {2}]
    assert suggestions == []
