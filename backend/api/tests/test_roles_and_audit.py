from datetime import date

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounts.masking import mask_dob, mask_email, mask_mobile
from audit.models import AuditEvent
from ingestion.models import SourceRecord
from mdm.models import Customer, MatchSuggestion
from mdm.services import build_customers
from sources.models import Source


def client_for(role_group):
    user = User.objects.create_user(f"user-{role_group or 'none'}", password="pass-1234")
    if role_group:
        user.groups.add(Group.objects.get(name=role_group))
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def suresh(db):
    dob = date(1984, 7, 12)
    for code, rid, name, mobile, email in [
        ("flexcube", "FX1", "Suresh Kumar", "9822104521", "suresh.kumar@mail.example"),
        ("branch_csv", "BR1", "Suresh K", "9822107788", "suresh.kumar@mail.example"),
    ]:
        SourceRecord.objects.create(source=Source.objects.get(code=code), source_record_id=rid, name=name,
                                    mobile=mobile, email=email, dob=dob)
    build_customers()
    return Customer.objects.get()


def test_maskers():
    assert mask_mobile("9822104521") == "98xxxx4521"
    assert mask_email("suresh.kumar@mail.example") == "s•••@mail.example"
    assert mask_dob("1984-07-12") == "1984-••-••"
    assert mask_mobile("") == ""


def test_agent_sees_masked_contact_details(suresh):
    body = client_for("Contact centre agent").get(f"/api/customers/{suresh.id}/").json()
    golden = {g["field"]: g["value"] for g in body["golden"]}
    assert body["masked"] is True
    assert golden["mobile"] == "98xxxx4521"
    assert golden["email"] == "s•••@mail.example"
    assert golden["dob"] == "1984-••-••"
    assert golden["name"] == "Suresh Kumar"  # name is needed to serve the customer
    assert all("x" in r["mobile"] for r in body["records"])  # source rows are masked too


def test_relationship_manager_sees_full_contact_details(suresh):
    body = client_for("Relationship manager").get(f"/api/customers/{suresh.id}/").json()
    assert body["masked"] is False
    assert {g["field"]: g["value"] for g in body["golden"]}["mobile"] == "9822104521"


def test_account_without_role_sees_nothing_but_itself(suresh):
    c = client_for(None)
    assert c.get("/api/customers/").status_code == 403
    me = c.get("/api/auth/me/").json()
    assert me["role"] is None and me["capabilities"] == []


@pytest.mark.parametrize(
    "group, sync_ok, review_ok, audit_ok, export_ok",
    [
        ("Relationship manager", False, False, False, False),
        ("Contact centre agent", False, False, False, False),
        ("Data steward", True, True, False, True),
        ("Compliance officer", False, True, True, True),
    ],
)
def test_capabilities_per_role(suresh, monkeypatch, group, sync_ok, review_ok, audit_ok, export_ok):
    import api.views
    from ingestion.sync import SyncResult

    monkeypatch.setattr(api.views, "sync_source", lambda code: SyncResult(fetched=0))
    c = client_for(group)
    assert (c.post("/api/sources/flexcube/sync/").status_code == 200) is sync_ok
    assert (c.get("/api/suggestions/").status_code == 200) is review_ok
    assert (c.get("/api/audit/").status_code == 200) is audit_ok
    assert (c.get("/api/customers/export/").status_code == 200) is export_ok


def test_only_stewards_decide_matches(db):
    dob = date(1981, 9, 9)
    SourceRecord.objects.create(source=Source.objects.get(code="flexcube"), source_record_id="A",
                                name="Nandini V Rao", mobile="9741200765", dob=dob)
    SourceRecord.objects.create(source=Source.objects.get(code="salesforce"), source_record_id="B",
                                name="Nandhini Rao", mobile="9741255310", dob=dob)
    build_customers()
    suggestion = MatchSuggestion.objects.get()
    assert client_for("Compliance officer").post(f"/api/suggestions/{suggestion.id}/accept/").status_code == 403
    assert client_for("Data steward").post(f"/api/suggestions/{suggestion.id}/accept/").status_code == 200


def test_actions_are_audited(suresh):
    User.objects.create_user("rm", password="pass-1234").groups.add(Group.objects.get(name="Relationship manager"))
    c = APIClient()
    c.post("/api/auth/login/", {"username": "rm", "password": "wrong"})
    c.post("/api/auth/login/", {"username": "rm", "password": "pass-1234"})
    c.get(f"/api/customers/{suresh.id}/")
    c.post("/api/sources/flexcube/sync/")  # not allowed for this role
    c.post("/api/auth/logout/")

    actions = list(AuditEvent.objects.order_by("id").values_list("action", flat=True))
    assert actions == ["login_failed", "login", "view_customer", "denied", "logout"]
    view = AuditEvent.objects.get(action="view_customer")
    assert view.actor_name == "rm" and view.role == "relationship_manager" and view.target == suresh.code


def test_audit_events_cannot_be_changed_or_deleted(suresh):
    event = AuditEvent.objects.create(actor_name="x", action=AuditEvent.LOGIN)
    event.target = "edited"
    with pytest.raises(ValueError):
        event.save()
    with pytest.raises(ValueError):
        event.delete()


def test_export_has_no_contact_details(suresh):
    response = client_for("Data steward").get("/api/customers/export/")
    text = response.content.decode("utf-8-sig")
    assert "Suresh Kumar" in text
    assert "9822104521" not in text and "@" not in text
    assert AuditEvent.objects.filter(action="export").exists()


def test_repeat_views_within_a_minute_are_logged_once(suresh):
    c = client_for("Relationship manager")
    c.get(f"/api/customers/{suresh.id}/")
    c.get(f"/api/customers/{suresh.id}/")
    assert AuditEvent.objects.filter(action="view_customer").count() == 1


def test_reference_reflects_the_live_rules(suresh):
    body = client_for("Contact centre agent").get("/api/reference/").json()
    agent = next(r for r in body["roles"] if r["role"] == "agent")
    assert "view_pii" not in agent["capabilities"]
    assert body["weights"]["name"] == "0.14"
    assert body["matching"]["match_threshold"] == 70
    assert body["sources"][0]["code"] == "flexcube"
