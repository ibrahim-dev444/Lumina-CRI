"""Several customer tables on one database connector: add, suspend, resume and remove tables."""

import uuid

import psycopg
import pytest
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.db import connection
from rest_framework.test import APIClient

from ingestion.models import SourceRecord
from mdm.models import Customer


@pytest.fixture
def bank_db(db, settings):
    """A real schema with a retail and a corporate customer table; C1 exists in both (two different people)."""
    settings.CONNECTORS_ALLOW_PRIVATE_HOSTS = True
    cfg = django_settings.DATABASES["default"]
    schema = f"mt_{uuid.uuid4().hex[:8]}"
    params = dict(host=cfg["HOST"], port=cfg["PORT"], dbname=connection.settings_dict["NAME"], user=cfg["USER"],
                  password=cfg["PASSWORD"], autocommit=True)
    with psycopg.connect(**params) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
        conn.execute(f'CREATE TABLE "{schema}".retail (cust_id text, cust_name text, mobile text)')
        conn.execute(f"INSERT INTO \"{schema}\".retail VALUES ('C1', 'Asha Rao', '9000000201'), "
                     "('C2', 'Vikram Shetty', '9000000202')")
        conn.execute(f'CREATE TABLE "{schema}".corporate (client_no text, signatory text, phone text)')
        conn.execute(f"INSERT INTO \"{schema}\".corporate VALUES ('C1', 'Meera Pillai', '9000000301')")
    yield schema, cfg
    with psycopg.connect(**params) as conn:
        conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def connected(bank_db):
    schema, cfg = bank_db
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user("mt.admin", password="Strong-pass-123", is_superuser=True))
    code = admin.post("/api/connectors/", {
        "name": "Core banking", "connector_type": "postgresql", "trust": 85,
        "settings": {"host": cfg["HOST"], "port": str(cfg["PORT"]), "database": connection.settings_dict["NAME"],
                     "username": cfg["USER"], "password": cfg["PASSWORD"], "sslmode": "prefer"},
    }, format="json").json()["code"]
    assert admin.put(f"/api/connectors/{code}/mapping/", {
        "object": f"{schema}.retail", "id_column": "cust_id", "fields": {"name": "cust_name", "mobile": "mobile"},
    }, format="json").status_code == 200
    added = admin.put(f"/api/connectors/{code}/tables/", {
        "object": f"{schema}.corporate", "id_column": "client_no", "fields": {"name": "signatory", "mobile": "phone"},
    }, format="json")
    assert added.status_code == 200, added.json()
    assert added.json()["key"] == "t2"
    assert admin.post(f"/api/sources/{code}/sync/").json()["fetched"] == 3
    return admin, code, schema


def names():
    return sorted(Customer.objects.visible().filter(golden_fields__field="name")
                  .values_list("golden_fields__value", flat=True))


def test_every_table_is_read_and_the_same_id_stays_two_people(connected):
    _, code, _ = connected
    assert names() == ["Asha Rao", "Meera Pillai", "Vikram Shetty"]
    ids = dict(SourceRecord.objects.filter(source__code=code).values_list("source_record_id", "origin_table"))
    assert ids == {"C1": "main", "C2": "main", "t2:C1": "t2"}


def test_suspend_and_resume_a_table_keeps_customer_ids(connected):
    admin, code, _ = connected
    meera = Customer.objects.visible().get(golden_fields__value="Meera Pillai").id
    out = admin.post(f"/api/connectors/{code}/tables/status/", {"keys": ["t2"], "status": "suspended"}, format="json")
    assert out.status_code == 200 and out.json()["changed"] == 1
    assert names() == ["Asha Rao", "Vikram Shetty"] and Customer.objects.filter(id=meera).exists()
    admin.post(f"/api/connectors/{code}/tables/status/", {"keys": ["t2"], "status": "active"}, format="json")
    assert Customer.objects.visible().get(golden_fields__value="Meera Pillai").id == meera


def test_suspending_the_main_table_also_covers_rows_saved_before_tables_existed(connected):
    admin, code, _ = connected
    SourceRecord.objects.filter(source__code=code, origin_table="main").update(origin_table="")  # older rows
    admin.post(f"/api/connectors/{code}/tables/status/", {"keys": ["main"], "status": "suspended"}, format="json")
    assert names() == ["Meera Pillai"]


def test_remove_an_added_table_after_seeing_what_goes(connected):
    admin, code, _ = connected
    preview = admin.get(f"/api/connectors/{code}/tables/remove/?keys=t2").json()
    assert preview == {"tables": 1, "records": 1, "customers": 1, "conversations": 0, "corrections": 0}
    assert admin.post(f"/api/connectors/{code}/tables/remove/", {"keys": ["t2"]}, format="json").status_code == 400
    done = admin.post(f"/api/connectors/{code}/tables/remove/", {"keys": ["t2"], "confirm": True}, format="json")
    assert done.status_code == 200 and done.json()["mapping"].get("tables") == []
    assert names() == ["Asha Rao", "Vikram Shetty"]
    refused = admin.post(f"/api/connectors/{code}/tables/remove/", {"keys": ["main"], "confirm": True},
                         format="json")
    assert refused.status_code == 400 and "main table" in refused.json()["detail"]


def test_tables_are_checked_and_kept_when_the_main_mapping_changes(connected):
    admin, code, schema = connected
    twice = admin.put(f"/api/connectors/{code}/tables/", {
        "object": f"{schema}.corporate", "id_column": "client_no", "fields": {"name": "signatory"}}, format="json")
    assert twice.status_code == 400 and "already" in twice.json()["detail"]
    wrong = admin.put(f"/api/connectors/{code}/tables/", {
        "key": "t2", "object": f"{schema}.corporate", "id_column": "nope", "fields": {"name": "signatory"}},
        format="json")
    assert wrong.status_code == 400
    admin.put(f"/api/connectors/{code}/mapping/", {
        "object": f"{schema}.retail", "id_column": "cust_id", "fields": {"name": "cust_name"}}, format="json")
    source = admin.get("/api/sources/").json()["results"]
    mapping = next(s for s in source if s["code"] == code)["mapping"]
    assert [t["key"] for t in mapping["tables"]] == ["t2"]


def test_file_connectors_do_not_take_tables(db):
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user("mt.admin2", password="Strong-pass-123", is_superuser=True))
    code = admin.post("/api/connectors/", {"name": "Sheets", "connector_type": "file_upload", "trust": 40},
                      format="json").json()["code"]
    assert admin.put(f"/api/connectors/{code}/tables/", {"object": "x"}, format="json").status_code == 400

