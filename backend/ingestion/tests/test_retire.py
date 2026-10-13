"""Removing the built-in demo sources (DEMO_SOURCES=off on the hosted demo), and the cloud demo data's edge cases."""

import pytest
from django.contrib.auth.models import User
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from ingestion.clean import clean_mobile
from ingestion.cloud_demo_data import customers
from ingestion.models import SourceRecord
from ingestion.retire import plan, remove_demo_sources
from ingestion.sync import ingest_records
from mdm.matching import find_groups
from mdm.models import Customer, FieldCorrection, MatchSuggestion
from mdm.services import build_customers
from sources.models import Source

SURESH = {"id": "1", "name": "Suresh Kumar", "pan": "ABCPK1234F", "mobile": "9822104521", "dob": "1984-07-12"}
ONLY_DEMO = {"id": "2", "name": "Meera Pillai", "pan": "BDEPD2345G", "mobile": "9890012345", "dob": "1990-03-05"}
LOOKALIKE = {"id": "3", "name": "Meera Pilai", "mobile": "9123456780", "dob": "1990-03-05"}


@pytest.fixture
def mixed(db):
    """Suresh is in a demo source and a real one; Meera only in demo sources (with a review and a correction)."""
    flexcube = Source.objects.get(code="flexcube")
    cloud = Source.objects.create(code="cloud-core", name="Cloud core", category="Core banking", trust="0.80",
                                  connector_type="push_api")
    ingest_records(flexcube, [SURESH, ONLY_DEMO], started_by="test")
    ingest_records(Source.objects.get(code="salesforce"), [LOOKALIKE], started_by="test")
    ingest_records(cloud, [{**SURESH, "id": "C1"}], started_by="test")
    build_customers()
    meera = SourceRecord.objects.get(source=flexcube, source_record_id="2").customer_link.customer
    FieldCorrection.objects.create(customer=meera, field="email", value="m@mail.example", evidence_ref="form 1",
                                   reason="test", proposed_by_name="steward")
    assert MatchSuggestion.objects.exists()
    return cloud


def test_dry_run_changes_nothing(mixed):
    before = (Source.objects.count(), SourceRecord.objects.count(), Customer.objects.count())
    result = plan()
    assert (result.sources, result.records, result.corrections_removed) == (3, 3, 1)
    assert result.customers_removed == 2  # Meera's two records were not merged: they wait for review
    assert (Source.objects.count(), SourceRecord.objects.count(), Customer.objects.count()) == before


def test_removes_demo_sources_and_keeps_real_ones(mixed):
    result = remove_demo_sources()
    assert result.sources == 3 and result.records == 3
    assert not Source.objects.filter(connector_type__startswith="demo_").exists()
    assert list(SourceRecord.objects.values_list("source__code", flat=True)) == ["cloud-core"]
    # Suresh survives, now described by the real source only; Meera, her review and her correction are gone.
    assert Customer.objects.count() == 1
    assert Customer.objects.get().golden_fields.get(field="name").value == "Suresh Kumar"
    assert not MatchSuggestion.objects.exists() and not FieldCorrection.objects.exists()
    assert remove_demo_sources().sources == 0  # running again changes nothing


@pytest.fixture
def platform(db):
    with schema_context("public"):
        User.objects.create_user("ops", password="Platform-pass-2026", is_superuser=True, is_staff=True)
    c = APIClient()
    assert c.post("/api/platform/auth/login/", {"username": "ops", "password": "Platform-pass-2026"}).status_code == 200
    return c


def test_new_organization_has_no_demo_sources_when_they_are_off(platform, settings):
    settings.DEMO_SOURCES = False
    made = platform.post("/api/platform/organizations/", {"code": "kotak", "name": "Kotak Bank",
                                                          "admin_username": "kotak.admin"})
    assert made.status_code == 201, made.json()
    with schema_context("kotak"):
        assert not Source.objects.exists()


@pytest.mark.parametrize("bank, seeds", [("axis", (1, 3)), ("hdfc", (2, 3))])
def test_cloud_data_gives_review_work_but_keeps_family_apart(bank, seeds):
    records = [
        {"id": r["id"], "name": r["name"], "pan": r["pan"], "mobile": clean_mobile(r["mobile"]),
         "email": r["email"], "dob": r["dob"]}
        for seed in seeds for r in customers(bank, seed=seed)
    ]
    groups, _, suggestions = find_groups(records)
    assert len(suggestions) == 2  # the typo duplicate and the person without a PAN in two systems
    family = next(r for r in records if r["name"] in ("Lata Iyer", "Sana Shaikh"))
    assert any(group == {family["id"]} for group in groups)  # shares a phone, but never merged
