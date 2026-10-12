"""The connector engine: catalog, secrets, safety checks, discovery, mapping and real reads."""

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import psycopg
import pytest
from django.conf import settings as django_settings
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from rest_framework.test import APIClient

from audit.models import AuditEvent
from ingestion.connectors.adapters import ConnectorError, PostgresAdapter, RestApiAdapter, _checked, _flatten
from ingestion.connectors.catalog import read_secrets
from ingestion.models import RawRecord, SourceRecord
from sources.models import Source, SyncRun


@pytest.fixture
def admin(db):
    c = APIClient()
    c.force_authenticate(User.objects.create_user("conn.admin", password="Strong-pass-123", is_superuser=True))
    return c


@pytest.fixture
def private_hosts_allowed(settings):
    settings.CONNECTORS_ALLOW_PRIVATE_HOSTS = True


def test_catalog_lists_every_type_without_code(admin):
    types = {t["type"]: t for t in admin.get("/api/connectors/catalog/").json()}
    assert {"postgresql", "mysql", "mongodb", "rest_api", "file_upload", "salesforce"} <= set(types)
    assert "adapter" not in types["postgresql"]
    assert any(f["secret"] for f in types["postgresql"]["fields"])


def test_only_admins_set_up_connectors(db):
    steward = User.objects.create_user("st.c", password="Strong-pass-123")
    steward.groups.add(Group.objects.get(name="Data steward"))
    c = APIClient()
    c.force_authenticate(steward)
    made = c.post("/api/connectors/", {"name": "X", "connector_type": "file_upload"}, format="json")
    assert made.status_code == 403


def test_password_is_encrypted_and_never_returned(admin):
    made = admin.post(
        "/api/connectors/",
        {"name": "Core replica", "connector_type": "postgresql", "trust": 80,
         "settings": {"host": "db.example.com", "port": "5432", "database": "core", "username": "reader",
                      "password": "S3cret-Pass!", "sslmode": "require"}},
        format="json",
    )
    assert made.status_code == 201, made.json()
    body = made.json()
    assert body["has_secret"] and "S3cret" not in json.dumps(body) and body["config"]["host"] == "db.example.com"
    source = Source.objects.get(code=body["code"])
    assert "S3cret" not in source.secret and read_secrets(source) == {"password": "S3cret-Pass!"}
    assert "S3cret" not in json.dumps(AuditEvent.objects.get(action="connector_added").detail)
    # Saving the form again with an empty password keeps the stored one.
    admin.patch(f"/api/connectors/{body['code']}/", {"settings": {"password": "", "port": "6543"}}, format="json")
    source.refresh_from_db()
    assert read_secrets(source) == {"password": "S3cret-Pass!"} and source.config["port"] == "6543"


def test_private_addresses_are_refused(admin, settings):
    settings.CONNECTORS_ALLOW_PRIVATE_HOSTS = False
    for host in ["127.0.0.1", "localhost", "10.0.0.5", "169.254.169.254"]:
        adapter = PostgresAdapter({"host": host, "database": "x", "username": "y"}, {"password": "z"})
        with pytest.raises(ConnectorError, match="private or internal"):
            adapter.list_objects()


def test_demo_connectors_cannot_be_reconfigured(admin):
    assert admin.post("/api/connectors/flexcube/test/").status_code == 400


def test_only_known_columns_reach_a_query():
    with pytest.raises(ConnectorError, match="Unknown column"):
        _checked(["name", "name; DROP TABLE x"], ["name", "mobile"])
    assert _flatten({"a": {"b": 1}, "c": 2}) == {"a.b": 1, "c": 2}


CSV = (
    "Ref,Full Name,Phone,PAN Number,Changed\n"
    "R1,Meera Iyer,9876543210,ABCPI1234K,2026-09-01\n"
    "R2,Rahul Bose,9811111111,,01/09/2026\n"
    ",No Id Person,9800000000,,\n"
)


def test_file_upload_end_to_end(admin):
    code = admin.post("/api/connectors/", {"name": "Branch sheet", "connector_type": "file_upload", "trust": 40},
                      format="json").json()["code"]
    upload = SimpleUploadedFile("branch.csv", CSV.encode("utf-8-sig"), content_type="text/csv")
    assert admin.post(f"/api/connectors/{code}/upload/", {"file": upload}, format="multipart").json()["rows"] == 3
    columns = admin.post(f"/api/connectors/{code}/discover/", {"object": "branch.csv"}, format="json").json()["columns"]
    assert columns == ["Ref", "Full Name", "Phone", "PAN Number", "Changed"]

    bad = admin.put(f"/api/connectors/{code}/mapping/",
                    {"object": "branch.csv", "id_column": "Ref", "fields": {"name": "Nope"}}, format="json")
    assert bad.status_code == 400
    mapped = admin.put(
        f"/api/connectors/{code}/mapping/",
        {"object": "branch.csv", "id_column": "Ref", "updated_column": "Changed",
         "fields": {"name": "Full Name", "mobile": "Phone", "pan": "PAN Number"}},
        format="json",
    )
    assert mapped.status_code == 200, mapped.json()

    synced = admin.post(f"/api/sources/{code}/sync/")
    assert synced.status_code == 200, synced.json()
    assert synced.json()["fetched"] == 3
    records = SourceRecord.objects.filter(source__code=code)
    assert sorted(r.name for r in records) == ["Meera Iyer", "Rahul Bose"]  # the row without an ID is skipped
    raw = RawRecord.objects.get(source__code=code, source_record_id="R1").payload
    assert "ABCPI1234K" not in json.dumps(raw)  # PAN encrypted in the raw copy too
    assert SyncRun.objects.get(source__code=code).status == SyncRun.OK
    runs = admin.get(f"/api/connectors/{code}/runs/").json()
    assert runs[0]["created"] == 2


def test_failed_sync_is_in_the_history(admin):
    code = admin.post("/api/connectors/", {"name": "Empty sheet", "connector_type": "file_upload"},
                      format="json").json()["code"]
    assert admin.post(f"/api/sources/{code}/sync/").status_code == 400  # no mapping yet
    run = SyncRun.objects.get(source__code=code)
    assert run.status == SyncRun.FAILED and "mapping" in run.error


@pytest.fixture
def scratch_table(db):
    """A real table in a throwaway schema of the test database server, created on its own connection
    (the test's own transaction is invisible to the connector's separate connection)."""
    db_settings = django_settings.DATABASES["default"]
    schema = f"conn_{uuid.uuid4().hex[:8]}"
    params = dict(host=db_settings["HOST"], port=db_settings["PORT"], dbname=connection.settings_dict["NAME"],
                  user=db_settings["USER"], password=db_settings["PASSWORD"], autocommit=True)
    with psycopg.connect(**params) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
        conn.execute(f'CREATE TABLE "{schema}".customers (cust_id text, cust_name text, mobile text, secret_note text)')
        conn.execute(f"INSERT INTO \"{schema}\".customers VALUES ('C1', 'Asha Rao', '9000000001', 'do not read')")
    yield schema, db_settings
    with psycopg.connect(**params) as conn:
        conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_postgres_reads_only_mapped_columns(scratch_table, private_hosts_allowed):
    schema, db = scratch_table
    adapter = PostgresAdapter(
        {"host": db["HOST"], "port": db["PORT"], "database": connection.settings_dict["NAME"], "username": db["USER"],
         "sslmode": "prefer"},
        {"password": db["PASSWORD"]},
    )
    assert f"{schema}.customers" in adapter.list_objects()
    assert adapter.list_columns(f"{schema}.customers") == ["cust_id", "cust_name", "mobile", "secret_note"]
    rows = adapter.fetch(f"{schema}.customers", ["cust_id", "cust_name"], 10)
    assert rows == [{"cust_id": "C1", "cust_name": "Asha Rao"}]  # secret_note never read


class _Api(BaseHTTPRequestHandler):
    PEOPLE = [{"id": i, "profile": {"name": f"Person {i}"}, "phone": f"98000000{i:02d}"} for i in range(1, 6)]

    def do_GET(self):  # noqa: N802
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(self.path).query)
        page, size = int(q.get("page", ["1"])[0]), int(q.get("per_page", ["2"])[0])
        auth_ok = self.headers.get("Authorization") == "Bearer t0ken"
        body = {"data": {"customers": self.PEOPLE[(page - 1) * size: page * size]}} if auth_ok else {"error": "no"}
        self.send_response(200 if auth_ok else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        pass


def test_rest_api_follows_pages_with_token(private_hosts_allowed):
    server = HTTPServer(("127.0.0.1", 0), _Api)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        config = {"url": f"http://127.0.0.1:{server.server_port}/customers", "records_path": "data.customers",
                  "auth": "bearer", "page_param": "page", "page_size_param": "per_page", "page_size": "2"}
        adapter = RestApiAdapter(config, {"token": "t0ken"})
        assert adapter.list_columns("records") == ["id", "profile.name", "phone"]
        rows = adapter.fetch("records", ["id", "profile.name"], 100)
        assert [r["profile.name"] for r in rows] == [f"Person {i}" for i in range(1, 6)]
        with pytest.raises(ConnectorError, match="401"):
            RestApiAdapter(config, {"token": "wrong"}).list_columns("records")
    finally:
        server.shutdown()
