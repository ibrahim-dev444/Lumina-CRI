"""Snowflake, Databricks, ServiceNow, Salesforce and Cloudera adapters, each against a small fake of the real API
(same paths, sign-in, paging and answer shapes), plus the safety rules every adapter keeps."""

import base64
from datetime import date
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from ingestion.connectors.adapters import ConnectorError
from ingestion.connectors.enterprise import (ClouderaAdapter, DatabricksAdapter, SalesforceAdapter, ServiceNowAdapter,
                                             SnowflakeAdapter)
from ingestion.models import SourceRecord


class Fake:
    """A local HTTP server; `routes` maps (method, path) to a function(request) -> (status, json)."""

    def __init__(self, routes):
        self.routes, self.seen = routes, []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self, method):
                parts = urllib.parse.urlparse(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode() if length else ""
                request = {"path": parts.path, "query": dict(urllib.parse.parse_qsl(parts.query)), "body": body,
                           "headers": dict(self.headers)}
                fake.seen.append(request)
                route = fake.routes.get((method, parts.path))
                status, payload = route(request) if route else (404, {"message": "no route"})
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):  # noqa: N802
                self._answer("GET")

            def do_POST(self):  # noqa: N802
                self._answer("POST")

            def do_DELETE(self):  # noqa: N802
                self._answer("DELETE")

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()


@pytest.fixture
def private_hosts(settings):
    settings.CONNECTORS_ALLOW_PRIVATE_HOSTS = True


@pytest.fixture
def fake():
    servers = []

    def start(routes):
        servers.append(Fake(routes))
        return servers[-1]

    yield start
    for s in servers:
        s.close()


# ---------- Snowflake ----------

@pytest.fixture
def rsa_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    return key, pem


def _jwt_claims(headers):
    token = headers["Authorization"].removeprefix("Bearer ")
    claims = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))


def test_snowflake_signs_in_with_key_pair_and_reads_only_mapped_columns(private_hosts, fake, rsa_key):
    statements = []

    def run(req):
        body = json.loads(req["body"])
        statements.append(body)
        sql = body["statement"]
        if "information_schema.tables" in sql:
            return 200, {"resultSetMetaData": {"rowType": [{"name": "T", "type": "text"}]},
                         "data": [["CORE.CUSTOMERS"]]}
        if "information_schema.columns" in sql:
            return 200, {"resultSetMetaData": {"rowType": [{"name": "C", "type": "text"}]},
                         "data": [["CUST_ID"], ["FULL_NAME"], ["DOB"], ["SECRET_NOTE"]]}
        return 202, {"statementHandle": "h-1"}  # the data query runs asynchronously

    def poll(req):
        return 200, {"resultSetMetaData": {"rowType": [{"name": "CUST_ID", "type": "text"},
                                                       {"name": "DOB", "type": "date"}],
                                           "partitionInfo": [{}, {}]},
                     "data": [["C1", "5306"]]}

    def partition(req):
        return 200, {"data": [["C2", None]]}

    server = fake({("POST", "/api/v2/statements"): run, ("GET", "/api/v2/statements/h-1"): lambda r:
                   partition(r) if r["query"].get("partition") else poll(r)})
    key, pem = rsa_key
    adapter = SnowflakeAdapter({"account": server.url, "username": "lumina_reader", "warehouse": "WH",
                                "database": "BANK", "role": "READER"},
                               {"private_key": pem.replace("\n", " ")})  # pasted on one line
    assert adapter.list_objects() == ["CORE.CUSTOMERS"]
    rows = adapter.fetch("CORE.CUSTOMERS", ["CUST_ID", "DOB"], 100)
    assert rows == [{"CUST_ID": "C1", "DOB": date(1984, 7, 12)}, {"CUST_ID": "C2", "DOB": None}]
    select = statements[-1]["statement"]
    assert select == 'SELECT "CUST_ID", "DOB" FROM "CORE"."CUSTOMERS" LIMIT 100' and "SECRET_NOTE" not in select
    assert statements[1]["bindings"] == {"1": {"type": "TEXT", "value": "CORE"}, "2": {"type": "TEXT",
                                                                                     "value": "CUSTOMERS"}}
    claims = _jwt_claims(server.seen[0]["headers"])
    assert claims["sub"].endswith(".LUMINA_READER") and ".SHA256:" in claims["iss"]
    assert statements[0]["role"] == "READER" and statements[0]["warehouse"] == "WH"
    with pytest.raises(ConnectorError, match="Unknown column"):
        adapter.fetch("CORE.CUSTOMERS", ['CUST_ID" FROM X; --'], 10)


def test_snowflake_needs_a_readable_key(private_hosts):
    adapter = SnowflakeAdapter({"account": "http://127.0.0.1:1", "username": "u", "warehouse": "w",
                                "database": "d"}, {"private_key": "not a key"})
    with pytest.raises(ConnectorError, match="private key"):
        adapter.list_objects()


# ---------- Databricks ----------

def test_databricks_runs_statements_and_follows_result_chunks(private_hosts, fake):
    sent = []

    def statements(req):
        body = json.loads(req["body"])
        sent.append(body)
        assert req["headers"]["Authorization"] == "Bearer dapi-token"
        sql = body["statement"]
        if "information_schema.tables" in sql:
            return 200, {"status": {"state": "SUCCEEDED"}, "manifest": {"schema": {"columns": [{"name": "t"}]}},
                         "result": {"data_array": [["bank.core.customers"]]}}
        if "information_schema.columns" in sql:
            return 200, {"status": {"state": "SUCCEEDED"}, "manifest": {"schema": {"columns": [{"name": "c"}]}},
                         "result": {"data_array": [["cust_id"], ["cust_name"], ["notes"]]}}
        return 200, {"status": {"state": "SUCCEEDED"},
                     "manifest": {"schema": {"columns": [{"name": "cust_id"}, {"name": "cust_name"}]}},
                     "result": {"data_array": [["C1", "Asha Rao"]],
                                "next_chunk_internal_link": "/api/2.0/sql/statements/s1/result/chunks/1"}}

    server = fake({("POST", "/api/2.0/sql/statements"): statements,
                   ("GET", "/api/2.0/sql/statements/s1/result/chunks/1"):
                       lambda r: (200, {"data_array": [["C2", "Vikram Shetty"]]})})
    adapter = DatabricksAdapter({"host": server.url, "warehouse_id": "wh-1"}, {"token": "dapi-token"})
    assert adapter.list_objects() == ["bank.core.customers"]
    rows = adapter.fetch("bank.core.customers", ["cust_id", "cust_name"], 50)
    assert [r["cust_name"] for r in rows] == ["Asha Rao", "Vikram Shetty"]
    assert sent[-1]["statement"] == "SELECT `cust_id`, `cust_name` FROM `bank`.`core`.`customers` LIMIT 50"
    assert sent[1]["parameters"] == [{"name": "c", "value": "bank"}, {"name": "s", "value": "core"},
                                     {"name": "t", "value": "customers"}]
    assert sent[0]["warehouse_id"] == "wh-1"


def test_databricks_reports_failed_statements(private_hosts, fake):
    server = fake({("POST", "/api/2.0/sql/statements"): lambda r: (200, {
        "status": {"state": "FAILED", "error": {"message": "TABLE_OR_VIEW_NOT_FOUND"}}})})
    with pytest.raises(ConnectorError, match="TABLE_OR_VIEW_NOT_FOUND"):
        DatabricksAdapter({"host": server.url, "warehouse_id": "w"}, {"token": "t"}).list_objects()


# ---------- ServiceNow ----------

CONTACTS = [{"sys_id": f"s{i}", "name": f"Person {i}", "mobile_phone": f"98000000{i:02d}", "u_secret": "x"}
            for i in range(1, 4)]


def _servicenow(req):
    assert req["headers"]["Authorization"] == "Basic " + base64.b64encode(b"reader:pw").decode()
    fields = req["query"].get("sysparm_fields")
    rows = [{k: v for k, v in c.items() if not fields or k in fields.split(",")} for c in CONTACTS]
    offset, limit = int(req["query"].get("sysparm_offset", 0)), int(req["query"]["sysparm_limit"])
    return 200, {"result": rows[offset:offset + limit]}


def test_servicenow_reads_mapped_fields_with_paging(private_hosts, fake):
    server = fake({("GET", "/api/now/table/customer_contact"): _servicenow})
    adapter = ServiceNowAdapter({"instance": server.url, "username": "reader", "table": "customer_contact"},
                                {"password": "pw"})
    adapter.PAGE = 2
    assert adapter.list_objects() == ["customer_contact"]
    assert adapter.list_columns("customer_contact") == ["sys_id", "name", "mobile_phone", "u_secret"]
    rows = adapter.fetch("customer_contact", ["sys_id", "name"], 100)
    assert [r["sys_id"] for r in rows] == ["s1", "s2", "s3"] and all("u_secret" not in r for r in rows)
    assert server.seen[-1]["query"]["sysparm_fields"] == "sys_id,name"
    with pytest.raises(ConnectorError, match="Table names"):
        adapter.fetch("customer_contact; drop", ["sys_id"], 10)


# ---------- Salesforce ----------

def test_salesforce_uses_client_credentials_describe_and_soql_paging(private_hosts, fake):
    def token(req):
        form = dict(urllib.parse.parse_qsl(req["body"]))
        assert form == {"grant_type": "client_credentials", "client_id": "key", "client_secret": "shh"}
        return 200, {"access_token": "00D!tok"}

    def authed(answer):
        def route(req):
            assert req["headers"]["Authorization"] == "Bearer 00D!tok"
            return answer(req)
        return route

    base = "/services/data/v62.0"
    server = fake({
        ("POST", "/services/oauth2/token"): token,
        ("GET", f"{base}/sobjects"): authed(lambda r: (200, {"sobjects": [
            {"name": "Contact", "queryable": True, "retrieveable": True},
            {"name": "Opportunity", "queryable": True, "retrieveable": True},
            {"name": "Customer_Profile__c", "queryable": True, "retrieveable": True}]})),
        ("GET", f"{base}/sobjects/Contact/describe"): authed(lambda r: (200, {"fields": [
            {"name": "Id", "type": "id"}, {"name": "Name", "type": "string"}, {"name": "Birthdate", "type": "date"},
            {"name": "MailingAddress", "type": "address"}, {"name": "MailingCity", "type": "string"}]})),
        ("GET", f"{base}/query"): authed(lambda r: (200, {
            "records": [{"attributes": {}, "Id": "003A", "Name": "Asha Rao"}],
            "nextRecordsUrl": f"{base}/query/01g-2000"})),
        ("GET", f"{base}/query/01g-2000"): authed(lambda r: (200, {"records": [{"Id": "003B", "Name": "Ravi"}]})),
    })
    adapter = SalesforceAdapter({"domain": server.url, "client_id": "key"}, {"client_secret": "shh"})
    assert adapter.list_objects() == ["Contact", "Customer_Profile__c"]
    assert adapter.list_columns("Contact") == ["Id", "Name", "Birthdate", "MailingCity"]  # compound left out
    rows = adapter.fetch("Contact", ["Id", "Name"], 100)
    assert rows == [{"Id": "003A", "Name": "Asha Rao"}, {"Id": "003B", "Name": "Ravi"}]
    soql = [s for s in server.seen if s["path"] == f"{base}/query"][0]["query"]["q"]
    assert soql == "SELECT Id, Name FROM Contact LIMIT 100"
    with pytest.raises(ConnectorError, match="Choose an object"):
        adapter.list_columns("Contact WHERE 1=1")


def test_salesforce_explains_a_rejected_app(private_hosts, fake):
    server = fake({("POST", "/services/oauth2/token"): lambda r: (400, {
        "error": "invalid_client", "error_description": "invalid client credentials"})})
    with pytest.raises(ConnectorError, match="invalid client credentials"):
        SalesforceAdapter({"domain": server.url, "client_id": "k"}, {"client_secret": "s"}).list_objects()


# ---------- Cloudera ----------

class _Cursor:
    def __init__(self, log):
        self.log, self.description, self._rows = log, None, []

    def execute(self, sql):
        self.log.append(sql)
        if sql.startswith("SHOW TABLES"):
            self.description, self._rows = [("tab_name",)], [("customers",)]
        elif sql.startswith("DESCRIBE"):
            self.description = [("col_name",), ("data_type",), ("comment",)]
            self._rows = [("cust_id", "string", ""), ("cust_name", "string", ""), ("", None, None),
                          ("# Partition Information", None, None)]
        else:
            self.description, self._rows = [("customers.cust_id",), ("customers.cust_name",)], [("C1", "Asha Rao")]

    def fetchall(self):
        return self._rows


def test_cloudera_reads_hive_tables_over_https(private_hosts, monkeypatch):
    import impala.dbapi

    log, opened = [], {}

    class Conn:
        def cursor(self):
            return _Cursor(log)

        def close(self):
            pass

    def connect(**kwargs):
        opened.update(kwargs)
        return Conn()

    monkeypatch.setattr(impala.dbapi, "connect", connect)
    adapter = ClouderaAdapter({"host": "127.0.0.1", "port": "443", "transport": "http", "database": "bank",
                               "username": "reader"}, {"password": "pw"})
    assert adapter.list_objects() == ["bank.customers"]
    assert adapter.list_columns("bank.customers") == ["cust_id", "cust_name"]
    assert adapter.fetch("bank.customers", ["cust_name"], 5) == [{"cust_name": "Asha Rao"}]
    assert log[-1] == "SELECT `cust_name` FROM `bank`.`customers` LIMIT 5"
    assert opened["use_ssl"] and opened["use_http_transport"] and opened["auth_mechanism"] == "LDAP"
    with pytest.raises(ConnectorError, match="letters, numbers"):
        adapter.list_columns("bank.customers`; drop")


# ---------- Safety shared by all ----------

@pytest.mark.parametrize("adapter", [
    DatabricksAdapter({"host": "10.0.0.5", "warehouse_id": "w"}, {"token": "t"}),
    ServiceNowAdapter({"instance": "https://169.254.169.254", "username": "u", "table": "x"}, {"password": "p"}),
    SalesforceAdapter({"domain": "https://localhost", "client_id": "k"}, {"client_secret": "s"}),
    ClouderaAdapter({"host": "192.168.1.10", "database": "d", "username": "u"}, {"password": "p"}),
], ids=["databricks", "servicenow", "salesforce", "cloudera"])
def test_private_addresses_are_refused(adapter, settings):
    settings.CONNECTORS_ALLOW_PRIVATE_HOSTS = False
    with pytest.raises(ConnectorError, match="private or internal"):
        adapter.list_objects()


def test_plain_http_is_refused_outside_development(settings):
    settings.CONNECTORS_ALLOW_PRIVATE_HOSTS = False
    with pytest.raises(ConnectorError, match="https"):
        DatabricksAdapter({"host": "http://example.com", "warehouse_id": "w"}, {"token": "t"}).list_objects()


def test_servicenow_connector_end_to_end(db, private_hosts, fake):
    server = fake({("GET", "/api/now/table/customer_contact"): _servicenow})
    admin = APIClient()
    admin.force_authenticate(User.objects.create_user("sn.admin", password="Strong-pass-123", is_superuser=True))
    made = admin.post("/api/connectors/", {"name": "Service desk", "connector_type": "servicenow", "trust": 50,
                                          "settings": {"instance": server.url, "username": "reader",
                                                       "password": "pw", "table": "customer_contact"}},
                      format="json")
    assert made.status_code == 201, made.json()
    code = made.json()["code"]
    assert "pw" not in json.dumps(made.json())
    assert admin.post(f"/api/connectors/{code}/test/").json()["ok"]
    assert admin.put(f"/api/connectors/{code}/mapping/", {
        "object": "customer_contact", "id_column": "sys_id", "fields": {"name": "name", "mobile": "mobile_phone"},
    }, format="json").status_code == 200
    synced = admin.post(f"/api/sources/{code}/sync/")
    assert synced.status_code == 200 and synced.json()["fetched"] == 3
    assert SourceRecord.objects.filter(source__code=code).count() == 3


# ---------- Demo seeders (run by developers against free trial accounts) ----------

def test_databricks_seeder_creates_tables_and_rows(private_hosts, fake, monkeypatch):
    import io

    from ingestion import enterprise_seed

    sent = []

    def statements(req):
        sent.append(json.loads(req["body"])["statement"])
        return 200, {"status": {"state": "SUCCEEDED"}, "manifest": {"schema": {"columns": []}}, "result": {}}

    server = fake({("POST", "/api/2.0/sql/statements"): statements})
    answers = iter([server.url, "wh-1", "workspace"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(enterprise_seed.getpass, "getpass", lambda prompt="": "dapi-token")
    out = io.StringIO()
    enterprise_seed.seed_databricks(out, "axis", False)
    assert sent[0] == "CREATE SCHEMA IF NOT EXISTS `workspace`.lumina_demo"
    assert sent[2].startswith("INSERT INTO `workspace`.lumina_demo.customers VALUES ('AX5-1001', 'Suresh Kumar'")
    assert "300 customers" in out.getvalue()


def test_servicenow_seeder_replaces_its_own_records_only(private_hosts, fake, monkeypatch):
    import io

    from ingestion import enterprise_seed

    created, deleted = [], []
    server = fake({
        ("GET", "/api/now/table/customer_contact"): lambda r: (200, {"result": [{"sys_id": "old1"}]}),
        ("POST", "/api/now/table/customer_contact"): lambda r: (created.append(json.loads(r["body"])) or
                                                                (201, {"result": {}})),
    })
    server.routes[("DELETE", "/api/now/table/customer_contact/old1")] = lambda r: deleted.append(1) or (204, {})
    answers = iter([server.url, "admin", "customer_contact"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(enterprise_seed.getpass, "getpass", lambda prompt="": "pw")
    enterprise_seed.seed_servicenow(io.StringIO(), "hdfc", False)
    assert server.seen[0]["query"]["sysparm_query"] == "user_nameSTARTSWITHlumina.hdfc."
    assert len(created) == 300 and created[0]["user_name"] == "lumina.hdfc.hd6-1001"
