"""Sign-in lockout, idle sign-out, security headers, scheduled syncs and the push API."""

import json
from datetime import timedelta

import pytest
from django.conf import settings as django_settings
from django.contrib.auth.models import Group, User
from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from accounts.lockout import MAX_FAILURES, locked_for
from ingestion.models import RawRecord, SourceRecord
from mdm.models import Customer
from sources.models import Source, SyncRun


def steward(name="lock.me"):
    user = User.objects.create_user(name, password="Right-pass-123")
    user.groups.add(Group.objects.get(name="Data steward"))
    return user


# ---------- Sign-in lockout ----------

def test_five_wrong_passwords_lock_the_login(db):
    steward()
    c = APIClient()
    for _ in range(MAX_FAILURES):
        assert c.post("/api/auth/login/", {"username": "lock.me", "password": "wrong"}).status_code == 400
    locked = c.post("/api/auth/login/", {"username": "lock.me", "password": "Right-pass-123"})
    assert locked.status_code == 429 and "locked" in locked.json()["detail"]
    # Other people are not affected.
    steward("other.person")
    assert c.post("/api/auth/login/", {"username": "other.person", "password": "Right-pass-123"}).status_code == 200


def test_lock_rules():
    now = timezone.now()
    four = [now - timedelta(minutes=m) for m in range(4)]
    assert locked_for(four, now=now) == 0
    five = [now - timedelta(minutes=m) for m in range(5)]
    assert 1 <= locked_for(five, now=now) <= 15
    old = [now - timedelta(minutes=20 + m) for m in range(5)]
    assert locked_for(old, now=now) == 0  # the window has passed
    assert locked_for(five, last_success_at=now - timedelta(seconds=30), now=now) == 0  # signed in since


def test_platform_login_locks_too(db):
    with schema_context("public"):
        User.objects.create_user("ops.lock", password="Platform-pass-2026", is_superuser=True)
    c = APIClient()
    for _ in range(MAX_FAILURES):
        c.post("/api/platform/auth/login/", {"username": "ops.lock", "password": "nope"})
    assert c.post("/api/platform/auth/login/", {"username": "ops.lock", "password": "Platform-pass-2026"}).status_code == 429


# ---------- Idle sign-out and headers ----------

def test_idle_sign_out_after_30_minutes():
    assert django_settings.SESSION_COOKIE_AGE == 30 * 60
    assert "accounts.middleware.IdleTimeoutMiddleware" in django_settings.MIDDLEWARE


def test_public_requests_do_not_touch_a_bank_session(db):
    """Regression: the organization look-up (shared schema) must not replace the bank's session cookie."""
    steward("keep.me")
    c = APIClient()
    assert c.post("/t/axis/api/auth/login/", {"username": "keep.me", "password": "Right-pass-123"}).status_code == 200
    looked_up = c.get("/api/organizations/axis/")
    assert "sessionid" not in looked_up.cookies
    assert c.get("/t/axis/api/auth/me/").status_code == 200

    me = c.get("/t/axis/api/auth/me/")
    assert "sessionid" in me.cookies  # signed-in requests refresh the 30 minutes


def test_api_answers_carry_browser_protections(db):
    response = APIClient().get("/api/organizations/axis/")
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"


# ---------- Scheduled syncs ----------

@pytest.fixture
def scheduled(db):
    return Source.objects.create(code="sched", name="Scheduled", category="Files", trust="0.40",
                                 connector_type="file_upload", sync_every_hours=6)


def test_runner_needs_the_token(scheduled, settings):
    settings.SYNC_RUNNER_TOKEN = "runner-secret"
    c = APIClient()
    assert c.post("/api/internal/run-due-syncs/").status_code == 403
    assert c.post("/api/internal/run-due-syncs/", HTTP_X_SYNC_TOKEN="wrong").status_code == 403
    settings.SYNC_RUNNER_TOKEN = ""
    assert c.post("/api/internal/run-due-syncs/", HTTP_X_SYNC_TOKEN="").status_code == 403  # off when unset


def test_only_due_sources_sync(scheduled, settings, monkeypatch):
    calls = []
    monkeypatch.setattr("ingestion.sync.sync_source", lambda code, started_by="": calls.append(code))
    settings.SYNC_RUNNER_TOKEN = "runner-secret"
    body = APIClient().post("/api/internal/run-due-syncs/", HTTP_X_SYNC_TOKEN="runner-secret").json()
    assert "sched" in calls and body["synced"] >= 1 and set(body) == {"organizations", "synced", "failed"}

    calls.clear()
    with schema_context("axis"):
        Source.objects.filter(code="sched").update(last_synced_at=timezone.now() - timedelta(hours=1))
    APIClient().post("/api/internal/run-due-syncs/", HTTP_X_SYNC_TOKEN="runner-secret")
    assert "sched" not in calls  # synced an hour ago, due again after 6


def test_schedule_must_be_a_known_interval(db):
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user("sched.admin", password="Strong-pass-123", is_superuser=True))
    assert admin.patch("/api/sources/flexcube/", {"sync_every_hours": 5}, format="json").status_code == 400
    assert admin.patch("/api/sources/flexcube/", {"sync_every_hours": 12}, format="json").json()["sync_every_hours"] == 12


# ---------- Push API ----------

@pytest.fixture
def push(db):
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user("push.admin", password="Strong-pass-123", is_superuser=True))
    code = admin.post("/api/connectors/", {"name": "Mobile app", "connector_type": "push_api", "trust": 50},
                      format="json").json()["code"]
    key = admin.post(f"/api/connectors/{code}/api-key/").json()["api_key"]
    return admin, code, key


RECORDS = {"records": [
    {"id": "APP-1", "name": "Asha Rao", "mobile": "9000000001", "pan": "ABCPR1234K", "updated_at": "2026-10-01T10:00:00"},
    {"id": "APP-2", "name": "Bala Iyer", "email": "bala@mail.example"},
]}


def send(code, key, body=RECORDS, org="axis"):
    return APIClient().post(f"/t/{org}/api/ingest/{code}/", body, format="json", HTTP_AUTHORIZATION=f"Bearer {key}")


def test_push_stores_records_like_any_source(push):
    _, code, key = push
    sent = send(code, key)
    assert sent.status_code == 202, sent.json()
    assert sent.json() == {"received": 2, "created": 2, "updated": 0}
    assert sorted(SourceRecord.objects.filter(source__code=code).values_list("name", flat=True)) == ["Asha Rao", "Bala Iyer"]
    assert "ABCPR1234K" not in json.dumps(RawRecord.objects.get(source_record_id="APP-1").payload)
    assert Customer.objects.count() == 2
    assert SyncRun.objects.get(source__code=code).started_by.startswith("API key lum_")


def test_push_rejects_wrong_or_replaced_keys(push):
    admin, code, key = push
    assert send(code, "lum_wrong").status_code == 401
    assert send(code, "").status_code == 401
    assert send(code, key, org="hdfc").status_code == 401  # the key belongs to Axis's connector only
    new_key = admin.post(f"/api/connectors/{code}/api-key/").json()["api_key"]
    assert send(code, key).status_code == 401 and send(code, new_key).status_code == 202


def test_push_checks_every_record(push):
    _, code, key = push
    bad = send(code, key, {"records": [{"id": "X", "name": "Y", "salary": 9}, {"name": "No id"}]})
    assert bad.status_code == 400 and len(bad.json()["problems"]) == 2
    too_many = {"records": [{"id": str(i), "name": "N"} for i in range(1001)]}
    assert send(code, key, too_many).status_code == 400
    assert SourceRecord.objects.filter(source__code=code).count() == 0


def test_key_is_shown_once_and_stored_hashed(push):
    admin, code, key = push
    source = Source.objects.get(code=code)
    assert key not in source.secret and key not in json.dumps(source.config)
    listed = admin.get("/api/sources/").json()["results"]
    assert key not in json.dumps(listed)
