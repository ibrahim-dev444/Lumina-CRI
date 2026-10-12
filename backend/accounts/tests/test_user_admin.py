import base64

import pytest
from django.contrib.auth.models import Group, User
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from audit.models import AuditEvent


def staff(name, group=None, admin=False, password="Strong-pass-123"):
    user = User.objects.create_user(name, password=password, is_superuser=admin, is_staff=admin)
    if group:
        user.groups.add(Group.objects.get(name=group))
    return user


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def admin_client(db):
    return client_for(staff("admin.axis", admin=True))


def test_admin_adds_user_with_temporary_password(admin_client):
    made = admin_client.post(
        "/api/users/", {"username": "Priya.S", "first_name": "Priya", "last_name": "S", "role": "agent"}
    )
    assert made.status_code == 201
    body = made.json()
    assert body["username"] == "priya.s" and body["role"] == "agent" and body["must_change_password"]
    assert len(body["temporary_password"]) >= 12
    assert User.objects.get(username="priya.s").check_password(body["temporary_password"])
    assert AuditEvent.objects.filter(action="user_created", target="priya.s").exists()
    assert "temporary_password" not in str(AuditEvent.objects.get(action="user_created").detail)


def test_only_admins_manage_users(db):
    steward = client_for(staff("steward.x", "Data steward"))
    assert steward.get("/api/users/").status_code == 403
    assert steward.post("/api/users/", {"username": "x.y", "role": "agent"}).status_code == 403


def test_temporary_password_unlocks_only_the_change_password_screen(admin_client):
    made = admin_client.post("/api/users/", {"username": "ravi", "role": "relationship_manager"}).json()
    person = APIClient()
    assert person.post("/api/auth/login/", {"username": "ravi", "password": made["temporary_password"]}).status_code == 200
    assert person.get("/api/auth/me/").json()["must_change_password"] is True
    assert person.get("/api/customers/").status_code == 403
    changed = person.post(
        "/api/auth/change-password/",
        {"current_password": made["temporary_password"], "new_password": "Ravi-own-pass-2026"},
    )
    assert changed.status_code == 204
    assert person.get("/api/customers/").status_code == 200  # still signed in, now unlocked
    assert person.get("/api/auth/me/").json()["must_change_password"] is False


def test_change_password_rules(db):
    me = staff("meera")
    c = APIClient()
    c.post("/api/auth/login/", {"username": "meera", "password": "Strong-pass-123"})
    wrong = c.post("/api/auth/change-password/", {"current_password": "nope", "new_password": "Another-pass-9876"})
    assert wrong.status_code == 400
    weak = c.post("/api/auth/change-password/", {"current_password": "Strong-pass-123", "new_password": "123"})
    assert weak.status_code == 400
    me.refresh_from_db()
    assert me.check_password("Strong-pass-123")


def test_admin_changes_role_and_deactivates(admin_client):
    person = staff("arun", "Contact centre agent")
    assert admin_client.patch(f"/api/users/{person.id}/", {"role": "steward"}).json()["role"] == "steward"
    assert admin_client.patch(f"/api/users/{person.id}/", {"is_active": False}).json()["is_active"] is False
    assert APIClient().post("/api/auth/login/", {"username": "arun", "password": "Strong-pass-123"}).status_code == 400
    event = AuditEvent.objects.filter(action="user_updated", target="arun").first()
    assert event.detail["changes"]["is_active"] == [True, False]


def test_admin_cannot_lock_themselves_out(db):
    me = staff("solo.admin", admin=True)
    c = client_for(me)
    assert c.patch(f"/api/users/{me.id}/", {"is_active": False}).status_code == 400
    assert c.patch(f"/api/users/{me.id}/", {"role": "agent"}).status_code == 400
    other = staff("second.admin", admin=True)
    assert c.patch(f"/api/users/{other.id}/", {"role": "agent"}).json()["role"] == "agent"
    me.refresh_from_db()
    assert me.is_superuser  # still an admin: they are the last one


def test_reset_password_gives_new_temporary_password(admin_client):
    person = staff("kiran", "Data steward")
    reset = admin_client.post(f"/api/users/{person.id}/reset-password/").json()
    person.refresh_from_db()
    assert person.check_password(reset["temporary_password"]) and reset["must_change_password"]
    assert AuditEvent.objects.filter(action="password_reset", target="kiran").exists()


def test_users_of_another_bank_are_invisible(admin_client):
    with schema_context("hdfc"):
        staff("hdfc.only", "Data steward")
    names = [u["username"] for u in admin_client.get("/api/users/").json()]
    assert "hdfc.only" not in names


def test_duplicate_or_bad_username_refused(admin_client):
    staff("taken")
    assert admin_client.post("/api/users/", {"username": "taken", "role": "agent"}).status_code == 400
    assert admin_client.post("/api/users/", {"username": "a b", "role": "agent"}).status_code == 400
    assert admin_client.post("/api/users/", {"username": "fine.name", "role": "boss"}).status_code == 400


PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()


def test_admin_sets_and_removes_logo(admin_client):
    assert admin_client.put("/api/settings/logo/", {"logo": PNG}, format="json").status_code == 200
    assert APIClient().get("/api/organizations/axis/").json()["logo"].startswith("data:image/png")
    assert admin_client.put("/api/settings/logo/", {"logo": ""}, format="json").json()["logo"] == ""
    assert APIClient().get("/api/organizations/axis/").json()["logo"] == ""


@pytest.mark.parametrize(
    "logo",
    [
        "data:image/svg+xml;base64," + base64.b64encode(b"<svg onload='alert(1)'/>").decode(),
        "data:image/png;base64," + base64.b64encode(b"not really a png").decode(),
        "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 300_000).decode(),
        "https://evil.example/logo.png",
    ],
    ids=["svg", "fake-png", "too-big", "web-address"],
)
def test_bad_logos_refused(admin_client, logo):
    assert admin_client.put("/api/settings/logo/", {"logo": logo}, format="json").status_code == 400


def test_only_admins_change_settings(db):
    steward = client_for(staff("steward.z", "Data steward"))
    assert steward.put("/api/settings/logo/", {"logo": PNG}, format="json").status_code == 403
    assert steward.get("/api/settings/trust/").status_code == 403
