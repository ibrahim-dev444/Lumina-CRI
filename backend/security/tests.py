from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from audit.models import AuditEvent
from ingestion.clean import clean_aadhaar, clean_gender, clean_pan
from ingestion.models import RawRecord, SourceRecord
from ingestion.sync import _protect_raw, _protect_record
from mdm.matching import find_groups, score_pair
from mdm.models import Customer, FieldCorrection, GoldenField
from mdm.services import build_customers
from security import crypto
from security.fields import display, mask_pan
from sources.models import Source
from stewardship.services import decide, propose


# ---------- cleaning ----------

@pytest.mark.parametrize("raw, expected", [
    (" abcpk 1234 f ", "ABCPK1234F"), ("ABCPK1234", ""), ("12345ABCDE", ""), (None, ""),
])
def test_clean_pan(raw, expected):
    assert clean_pan(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("4821 7730 4521", "4521"), ("XXXX XXXX 9012", "9012"), ("12345", ""), ("", ""),
])
def test_aadhaar_keeps_only_last_four_digits(raw, expected):
    assert clean_aadhaar(raw) == expected


def test_clean_gender():
    assert [clean_gender(v) for v in ["M", "female", "x", None]] == ["Male", "Female", "", ""]


# ---------- encryption ----------

def test_encrypt_round_trip_and_fingerprint():
    token = crypto.encrypt("ABCPK1234F")
    assert token.startswith("enc:v1:") and "ABCPK1234F" not in token
    assert crypto.decrypt(token) == "ABCPK1234F"
    assert crypto.encrypt("ABCPK1234F") != token  # random each time, so ciphertexts cannot be compared
    assert crypto.fingerprint("ABCPK1234F") == crypto.fingerprint("ABCPK1234F")  # fingerprints can
    assert crypto.fingerprint("ABCPK1234F") != crypto.fingerprint("ABCPK1234G")


def test_raw_copy_never_holds_readable_identity_numbers():
    safe = _protect_raw({"PAN_NO": "ABCPK1234F", "AADHAAR_NO": "4821 7730 4521", "NAME": "Suresh"},
                        {"PAN_NO": "pan", "AADHAAR_NO": "aadhaar"})
    assert "ABCPK1234F" not in str(safe) and "4821" not in str(safe)
    assert safe["AADHAAR_NO"] == "XXXX XXXX 4521"
    assert crypto.decrypt(safe["PAN_NO"]) == "ABCPK1234F"


def test_cleaned_record_stores_pan_encrypted_with_fingerprint():
    std = _protect_record({"pan": "ABCPK1234F", "ckyc": ""})
    assert crypto.decrypt(std["pan"]) == "ABCPK1234F"
    assert std["pan_hash"] == crypto.fingerprint("ABCPK1234F")
    assert std["ckyc"] == "" and std["ckyc_hash"] == ""


def test_display_masks_identity_numbers():
    assert display("pan", crypto.encrypt("ABCPK1234F")) == mask_pan("ABCPK1234F") == "XXXXX1234X"
    assert display("aadhaar", "4521") == "XXXX XXXX 4521"
    assert display("name", "Suresh") == "Suresh"


# ---------- PAN matching ----------

def rec(id, name, pan="", mobile="", dob=None):
    return {"id": id, "name": name, "mobile": mobile, "email": "", "dob": dob,
            "pan": crypto.fingerprint(pan) if pan else ""}


def test_same_pan_merges_even_without_other_shared_details():
    groups, reasons, _ = find_groups([rec(1, "Rajesh R Iyer", "CFGPI3456H"), rec(2, "Rajesh Aiyar", "CFGPI3456H")])
    assert groups == [{1, 2}]
    assert "same PAN" in reasons[1]


def test_different_pans_are_never_merged():
    points, reason = score_pair(rec(1, "Suresh Kumar", "ABCPK1234F", "9822104521"),
                                rec(2, "Suresh Kumar", "ZZZPK1234F", "9822104521"))
    assert (points, reason) == (0, "different PAN")


# ---------- API: masking, reveal, corrections ----------

def add_record(code, rid, name, pan, dob=date(1984, 7, 12)):
    std = _protect_record({"pan": pan, "ckyc": ""})
    return SourceRecord.objects.create(source=Source.objects.get(code=code), source_record_id=rid, name=name,
                                       dob=dob, aadhaar="4521", **std)


def api_as(group, name):
    user = User.objects.create_user(name, password="pass-1234")
    user.groups.add(Group.objects.get(name=group))
    c = APIClient()
    c.force_authenticate(user)
    return c, user


@pytest.fixture
def suresh(db):
    add_record("flexcube", "FX1", "Suresh Kumar", "ABCPK1234F")
    build_customers()
    return Customer.objects.get()


def test_pan_is_masked_for_every_role_and_never_stored_plain(suresh):
    golden = GoldenField.objects.get(customer=suresh, field="pan")
    assert "ABCPK1234F" not in golden.value
    for group in ["Relationship manager", "Data steward", "Compliance officer"]:
        client, _ = api_as(group, group.split()[0].lower())
        body = client.get(f"/api/customers/{suresh.id}/").json()
        assert "ABCPK1234F" not in str(body)
        assert next(g for g in body["golden"] if g["field"] == "pan")["value"] == "XXXXX1234X"
        assert next(g for g in body["golden"] if g["field"] == "aadhaar")["value"] == "XXXX XXXX 4521"


def test_only_compliance_can_reveal_and_it_is_audited(suresh):
    steward, _ = api_as("Data steward", "steward")
    assert steward.post(f"/api/customers/{suresh.id}/reveal/", {"field": "pan", "reason": "Customer dispute"}).status_code == 403

    compliance, _ = api_as("Compliance officer", "compliance")
    assert compliance.post(f"/api/customers/{suresh.id}/reveal/", {"field": "pan", "reason": ""}).status_code == 400
    response = compliance.post(f"/api/customers/{suresh.id}/reveal/", {"field": "pan", "reason": "Customer dispute"})
    assert response.json() == {"field": "pan", "value": "ABCPK1234F"}
    event = AuditEvent.objects.get(action="reveal")
    assert event.actor_name == "compliance" and event.detail["reason"] == "Customer dispute"
    assert "ABCPK1234F" not in str(event.detail)  # the number itself is never logged


def test_pan_correction_is_encrypted_and_wins(suresh):
    _, maker = api_as("Relationship manager", "maker")
    _, checker = api_as("Data steward", "checker")
    c = propose(suresh, "pan", "abcpk 1234 g", "PAN card copy", "Last letter was mistyped", maker)
    assert "ABCPK1234G" not in c.value and c.previous_value == "XXXXX1234X"
    decide(c, approve=True, user=checker)
    golden = GoldenField.objects.get(customer=suresh, field="pan")
    assert golden.correction_id == c.id and crypto.decrypt(golden.value) == "ABCPK1234G"
    assert FieldCorrection.objects.count() == 1


def test_sync_keeps_raw_payload_safe(db, monkeypatch):
    from ingestion.connectors.flexcube import FlexcubeConnector
    from ingestion.sync import sync_source

    row = {"CUST_ID": "FX9", "CUST_NAME": "Test Person", "MOB_NO": "9822104521", "EMAIL_ID": None, "ADDR1": "Pune",
           "DOB": date(1990, 1, 1), "PAN_NO": "ABCPK1234F", "AADHAAR_NO": "1111 2222 3333", "CKYC_NO": "50012345678821",
           "LAST_UPD_DT": None}
    monkeypatch.setattr(FlexcubeConnector, "fetch", lambda self: [dict(row)])
    sync_source("flexcube")
    stored = str(RawRecord.objects.get().payload) + str(SourceRecord.objects.values().get())
    for secret in ["ABCPK1234F", "1111 2222", "111122223333", "50012345678821"]:
        assert secret not in stored
    assert SourceRecord.objects.get().aadhaar == "3333"
