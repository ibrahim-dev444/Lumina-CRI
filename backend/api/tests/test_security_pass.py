"""Rate limits, password hashing, the CSV formula guard and the hidden Django admin."""

import csv
import io

from django.contrib.auth.hashers import identify_hasher
from django.contrib.auth.models import Group, User
from django.urls import clear_url_caches
from rest_framework.test import APIClient

from ingestion.models import SourceRecord
from mdm.services import build_customers
from sources.models import Source


def test_sign_in_is_rate_limited_per_address(db):
    c = APIClient()
    answers = [c.post("/api/auth/login/", {"username": f"nobody{i}", "password": "x"}).status_code for i in range(11)]
    assert answers[:10] == [400] * 10 and answers[10] == 429


def test_new_passwords_are_hashed_with_argon2id(db):
    user = User.objects.create_user("argon.user", password="Strong-pass-123")
    assert identify_hasher(user.password).algorithm == "argon2" and "$argon2id$" in user.password


def test_exported_names_cannot_run_as_spreadsheet_formulas(db):
    SourceRecord.objects.create(source=Source.objects.get(code="flexcube"), source_record_id="X1",
                                name='=HYPERLINK("http://evil.example","Click")')
    build_customers()
    user = User.objects.create_user("exp.officer", password="Strong-pass-123")
    user.groups.add(Group.objects.get(name="Compliance officer"))
    c = APIClient()
    c.force_authenticate(user)
    rows = list(csv.reader(io.StringIO(c.get("/api/customers/export/").content.decode())))
    assert rows[1][1].startswith("'=HYPERLINK")


def test_django_admin_is_not_served_outside_development(db, settings):
    import importlib

    import config.urls_public

    settings.DEBUG = False
    importlib.reload(config.urls_public)
    clear_url_caches()
    assert not any(str(p.pattern) == "admin/" for p in config.urls_public.urlpatterns)
