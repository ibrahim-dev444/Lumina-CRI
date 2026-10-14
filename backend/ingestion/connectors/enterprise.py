"""Adapters for enterprise platforms: Snowflake, Databricks, ServiceNow, Salesforce and Cloudera.

The first four are read over their official HTTPS APIs (no extra libraries): Snowflake's SQL API with key-pair
sign-in, Databricks' SQL Statement Execution API with an access token, ServiceNow's Table API and Salesforce's
REST API with a connected app. Cloudera (Hive or Impala) is read through HiveServer2 with the impyla driver.

The same safety rules as every other adapter apply: public addresses only (security.network), no redirects,
time limits, row caps, and only column names that list_columns() returned are ever put into a query. The
platforms' own read-only roles (a SELECT-only role, a read-only user) are what the setup guide asks for.
"""

import base64
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from django.conf import settings

from security.network import BlockedAddress, check_host

from .adapters import BaseAdapter, ConnectorError, _checked, _flatten, _NoRedirects, _plain, _require, _timeout

MAX_PAGES = 200


def _base_url(value, default_suffix=""):
    """'xy12345' + '.snowflakecomputing.com' -> 'https://xy12345.snowflakecomputing.com'. A full https:// address
    is used as it is (private-link addresses, tests)."""
    value = (value or "").strip().rstrip("/")
    if not value:
        raise ConnectorError("Missing the server address.")
    if "://" not in value:
        value = "https://" + value + default_suffix
    parts = urllib.parse.urlparse(value)
    if parts.scheme != "https" and not (parts.scheme == "http" and settings.CONNECTORS_ALLOW_PRIVATE_HOSTS):
        raise ConnectorError("Use an https:// address.")
    try:
        check_host(parts.hostname, parts.port)
    except BlockedAddress as exc:
        raise ConnectorError(str(exc)) from exc
    return f"{parts.scheme}://{parts.netloc}"


def _http(method, url, headers=None, body=None, form=False):
    """One HTTPS call that answers JSON. Errors become ConnectorError with the platform's own message."""
    data = None
    headers = {"Accept": "application/json", "User-Agent": "Lumina-CRI-connector", **(headers or {})}
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirects)
    try:
        with opener.open(request, timeout=_timeout()) as response:
            raw = response.read(25 * 1024 * 1024 + 1)
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read(64 * 1024) or b"{}")
            if isinstance(payload, list) and payload:
                payload = payload[0]
            detail = (payload.get("message") or payload.get("error_description") or payload.get("error", {})
                      if isinstance(payload, dict) else "")
            if isinstance(detail, dict):
                detail = detail.get("message", "")
        except ValueError:
            pass
        raise ConnectorError(f"The server answered {exc.code}: {detail or exc.reason}".rstrip(": ")) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectorError(f"Could not reach the server: {getattr(exc, 'reason', exc)}") from exc
    if len(raw) > 25 * 1024 * 1024:
        raise ConnectorError("The answer is larger than 25 MB. Choose a smaller table or fewer columns.")
    try:
        return status, (json.loads(raw) if raw else {})
    except ValueError as exc:
        raise ConnectorError("The server did not answer with JSON.") from exc


def _three_part(obj, parts=3, example="catalog.schema.table"):
    names = (obj or "").split(".")
    if len(names) != parts or not all(names):
        raise ConnectorError(f"Choose a table, like {example}.")
    return names


# ---------- Snowflake (SQL API, key-pair sign-in) ----------

def _b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class SnowflakeAdapter(BaseAdapter):
    """Snowflake's SQL API signed in with a key pair: the bank gives the user an RSA public key, Lumina keeps the
    private key encrypted. Password-only sign-in is being retired by Snowflake, so it is not offered."""

    def _host_part(self):
        """'https://ORG-ACCT.snowflakecomputing.com' or 'org-acct' or 'xy12345.us-east-1' -> what goes before
        .snowflakecomputing.com."""
        _require(self.config, "account", "username", "warehouse", "database")
        return self.config["account"].strip().split("://")[-1].split(".snowflakecomputing.com")[0].strip("/")

    def _account(self):
        """The account name inside the sign-in token: the part before any region, upper case."""
        return self._host_part().split(".")[0].upper()

    def _token(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        pem = _pem(self.secrets.get("private_key", ""))
        if not pem:
            raise ConnectorError("Paste the private key (PEM) that matches the user's RSA public key.")
        try:
            key = serialization.load_pem_private_key(pem.encode(), password=None)
        except (ValueError, TypeError) as exc:
            raise ConnectorError("The private key could not be read. Paste an unencrypted PEM key.") from exc
        public = key.public_key().public_bytes(serialization.Encoding.DER,
                                               serialization.PublicFormat.SubjectPublicKeyInfo)
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(public).digest()).decode()
        user = f"{self._account()}.{self.config['username'].strip().upper()}"
        now = int(time.time())
        header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        claims = _b64url(json.dumps({"iss": f"{user}.{fingerprint}", "sub": user, "iat": now,
                                     "exp": now + 3000}).encode())
        signature = key.sign(f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
        return f"{header}.{claims}.{_b64url(signature)}"

    def _run(self, statement, bindings=None):
        account = self.config.get("account", "").strip()
        base = _base_url(account if account.startswith("http") else self._host_part().lower(),
                         ".snowflakecomputing.com")
        headers = {"Authorization": f"Bearer {self._token()}",
                   "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT"}
        body = {"statement": statement, "timeout": _timeout(), "warehouse": self.config["warehouse"],
                "database": self.config["database"]}
        if self.config.get("role"):
            body["role"] = self.config["role"]
        if bindings:
            body["bindings"] = {str(i + 1): {"type": "TEXT", "value": v} for i, v in enumerate(bindings)}
        status, answer = _http("POST", f"{base}/api/v2/statements", headers, body)
        handle = answer.get("statementHandle")
        deadline = time.monotonic() + _timeout()
        while status == 202 and handle and time.monotonic() < deadline:
            time.sleep(1)
            status, answer = _http("GET", f"{base}/api/v2/statements/{handle}", headers)
        if status == 202:
            raise ConnectorError("Snowflake did not finish in time. Use a larger warehouse or fewer rows.")
        meta = answer.get("resultSetMetaData") or {}
        types = [(c.get("name"), (c.get("type") or "").lower()) for c in meta.get("rowType", [])]
        rows = list(answer.get("data") or [])
        for n in range(1, len(meta.get("partitionInfo") or [])):
            _, more = _http("GET", f"{base}/api/v2/statements/{handle}?partition={n}", headers)
            rows.extend(more.get("data") or [])
        return [{name: _snowflake_value(kind, v) for (name, kind), v in zip(types, row)} for row in rows]

    def list_objects(self):
        rows = self._run("SELECT table_schema || '.' || table_name AS t FROM information_schema.tables "
                         "WHERE table_schema <> 'INFORMATION_SCHEMA' ORDER BY 1 LIMIT 500")
        return [r["T"] for r in rows]

    def list_columns(self, obj):
        schema, table = _three_part(obj, 2, "PUBLIC.CUSTOMERS")
        rows = self._run("SELECT column_name AS c FROM information_schema.columns WHERE table_schema = ? "
                         "AND table_name = ? ORDER BY ordinal_position", [schema, table])
        if not rows:
            raise ConnectorError(f"No table {obj}, or no permission to read it.")
        return [r["C"] for r in rows]

    def fetch(self, obj, columns, limit):
        schema, table = _three_part(obj, 2, "PUBLIC.CUSTOMERS")
        _checked(columns, self.list_columns(obj))
        quoted = ", ".join('"' + c.replace('"', '""') + '"' for c in columns)
        target = '"' + schema.replace('"', '""') + '"."' + table.replace('"', '""') + '"'
        return [{c: _plain(r.get(c)) for c in columns}
                for r in self._run(f"SELECT {quoted} FROM {target} LIMIT {int(limit)}")]


def _pem(text):
    """A PEM key pasted into a one-line box loses its line breaks; put them back."""
    text = (text or "").strip()
    match = re.match(r"^(-----BEGIN [A-Z ]+-----)\s*(.+?)\s*(-----END [A-Z ]+-----)$", text, re.S)
    if not match:
        return text
    body = re.sub(r"\s+", "", match.group(2))
    lines = [match.group(1), *[body[i:i + 64] for i in range(0, len(body), 64)], match.group(3)]
    return "\n".join(lines) + "\n"


def _snowflake_value(kind, value):
    """The SQL API sends every value as text: dates as days since 1970, timestamps as seconds."""
    if value is None:
        return None
    try:
        if kind == "date":
            return date(1970, 1, 1) + timedelta(days=int(value))
        if kind.startswith("timestamp"):
            return datetime.fromtimestamp(float(str(value).split()[0]), tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError):
        return value
    return value


# ---------- Databricks (SQL Statement Execution API) ----------

class DatabricksAdapter(BaseAdapter):
    def _run(self, statement, parameters=None):
        _require(self.config, "host", "warehouse_id")
        token = self.secrets.get("token", "")
        if not token:
            raise ConnectorError("Missing: access token.")
        base = _base_url(self.config["host"])
        headers = {"Authorization": f"Bearer {token}"}
        body = {"warehouse_id": self.config["warehouse_id"].strip(), "statement": statement, "wait_timeout": "30s",
                "on_wait_timeout": "CANCEL", "format": "JSON_ARRAY", "disposition": "INLINE"}
        if parameters:
            body["parameters"] = [{"name": k, "value": v} for k, v in parameters.items()]
        _, answer = _http("POST", f"{base}/api/2.0/sql/statements", headers, body)
        state = (answer.get("status") or {}).get("state")
        if state != "SUCCEEDED":
            error = ((answer.get("status") or {}).get("error") or {}).get("message", "")
            raise ConnectorError(f"Databricks: {state or 'no answer'}. {error}".strip())
        names = [c["name"] for c in ((answer.get("manifest") or {}).get("schema") or {}).get("columns", [])]
        result = answer.get("result") or {}
        rows = list(result.get("data_array") or [])
        link, pages = result.get("next_chunk_internal_link"), 0
        while link and pages < MAX_PAGES:
            _, chunk = _http("GET", base + link, headers)
            rows.extend(chunk.get("data_array") or [])
            link, pages = chunk.get("next_chunk_internal_link"), pages + 1
        return [dict(zip(names, row)) for row in rows]

    def list_objects(self):
        rows = self._run("SELECT concat_ws('.', table_catalog, table_schema, table_name) AS t "
                         "FROM system.information_schema.tables WHERE table_schema <> 'information_schema' "
                         "AND table_catalog <> 'system' ORDER BY 1 LIMIT 500")
        return [r["t"] for r in rows]

    def list_columns(self, obj):
        catalog, schema, table = _three_part(obj)
        rows = self._run("SELECT column_name AS c FROM system.information_schema.columns WHERE table_catalog = :c "
                         "AND table_schema = :s AND table_name = :t ORDER BY ordinal_position",
                         {"c": catalog, "s": schema, "t": table})
        if not rows:
            raise ConnectorError(f"No table {obj}, or no permission to read it.")
        return [r["c"] for r in rows]

    def fetch(self, obj, columns, limit):
        names = _three_part(obj)
        _checked(columns, self.list_columns(obj))

        def q(name):
            return "`" + name.replace("`", "``") + "`"

        statement = f"SELECT {', '.join(q(c) for c in columns)} FROM {'.'.join(q(n) for n in names)} LIMIT {int(limit)}"
        return [{c: _plain(r.get(c)) for c in columns} for r in self._run(statement)]


# ---------- ServiceNow (Table API) ----------

_TABLE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


class ServiceNowAdapter(BaseAdapter):
    PAGE = 1000

    def _get(self, path, params):
        _require(self.config, "instance", "username", "table")
        base = _base_url(self.config["instance"], ".service-now.com")
        login = f"{self.config['username']}:{self.secrets.get('password', '')}".encode()
        headers = {"Authorization": "Basic " + base64.b64encode(login).decode()}
        _, answer = _http("GET", f"{base}{path}?{urllib.parse.urlencode(params)}", headers)
        result = answer.get("result")
        if not isinstance(result, list):
            raise ConnectorError("ServiceNow did not return a list of records.")
        return result

    def _table(self, obj=None):
        table = (obj or self.config.get("table") or "").strip()
        if not _TABLE_NAME.match(table):
            raise ConnectorError("Table names look like customer_contact or sys_user.")
        return table

    def list_objects(self):
        table = self._table()
        self._get(f"/api/now/table/{table}", {"sysparm_limit": 1})  # proves the address, login and table work
        return [table]

    def list_columns(self, obj):
        rows = self._get(f"/api/now/table/{self._table(obj)}",
                         {"sysparm_limit": 20, "sysparm_exclude_reference_link": "true"})
        seen = []
        for row in rows:
            for key in _flatten(row):
                if key not in seen:
                    seen.append(key)
        if not seen:
            raise ConnectorError(f"The table {obj} is empty, or this user may not read it.")
        return seen

    def fetch(self, obj, columns, limit):
        table = self._table(obj)
        _checked(columns, self.list_columns(obj))
        rows, offset = [], 0
        while len(rows) < limit and offset // self.PAGE < MAX_PAGES:
            page = self._get(f"/api/now/table/{table}", {
                "sysparm_fields": ",".join(columns), "sysparm_limit": min(self.PAGE, limit - len(rows)),
                "sysparm_offset": offset, "sysparm_exclude_reference_link": "true",
            })
            rows.extend({c: _plain(_flatten(r).get(c)) for c in columns} for r in page)
            if len(page) < self.PAGE:
                break
            offset += self.PAGE
        return rows[:limit]


# ---------- Salesforce (REST API, connected app, client credentials) ----------

_SOBJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
API_VERSION = "v62.0"


class SalesforceAdapter(BaseAdapter):
    def _session(self):
        _require(self.config, "domain", "client_id")
        if not self.secrets.get("client_secret"):
            raise ConnectorError("Missing: consumer secret.")
        base = _base_url(self.config["domain"], ".my.salesforce.com")
        _, token = _http("POST", f"{base}/services/oauth2/token", body={
            "grant_type": "client_credentials", "client_id": self.config["client_id"].strip(),
            "client_secret": self.secrets["client_secret"],
        }, form=True)
        if not token.get("access_token"):
            raise ConnectorError("Salesforce did not give an access token. Check the connected app.")
        return base, {"Authorization": f"Bearer {token['access_token']}"}

    def _sobject(self, obj):
        if not _SOBJECT.match(obj or ""):
            raise ConnectorError("Choose an object, like Contact or Account.")
        return obj

    def list_objects(self):
        base, headers = self._session()
        _, answer = _http("GET", f"{base}/services/data/{API_VERSION}/sobjects", headers)
        found = [o["name"] for o in answer.get("sobjects", []) if o.get("queryable") and o.get("retrieveable")
                 and (o["name"] in ("Contact", "Account", "Lead") or o["name"].endswith("__c"))]
        return sorted(found, key=lambda n: (n not in ("Contact", "Account", "Lead"), n))

    def _describe(self, obj, session=None):
        base, headers = session or self._session()
        _, answer = _http("GET", f"{base}/services/data/{API_VERSION}/sobjects/{self._sobject(obj)}/describe",
                          headers)
        # Address and location are compound fields; their parts (MailingStreet, MailingCity...) are listed too.
        return [f["name"] for f in answer.get("fields", []) if f.get("type") not in ("address", "location")]

    def list_columns(self, obj):
        columns = self._describe(obj)
        if not columns:
            raise ConnectorError(f"No object {obj}, or this user may not read it.")
        return columns

    def fetch(self, obj, columns, limit):
        session = self._session()
        base, headers = session
        _checked(columns, self._describe(obj, session))
        soql = f"SELECT {', '.join(columns)} FROM {self._sobject(obj)} LIMIT {int(limit)}"
        _, answer = _http("GET", f"{base}/services/data/{API_VERSION}/query?{urllib.parse.urlencode({'q': soql})}",
                          headers)
        records, pages = list(answer.get("records") or []), 0
        while answer.get("nextRecordsUrl") and len(records) < limit and pages < MAX_PAGES:
            _, answer = _http("GET", base + answer["nextRecordsUrl"], headers)
            records.extend(answer.get("records") or [])
            pages += 1
        return [{c: _plain(r.get(c)) for c in columns} for r in records[:limit]]


# ---------- Cloudera (Hive or Impala over HiveServer2) ----------

_IDENT = re.compile(r"^[A-Za-z0-9_]{1,128}$")


class ClouderaAdapter(BaseAdapter):
    def _connect(self):
        from impala.dbapi import connect

        _require(self.config, "host", "username", "database")
        http = (self.config.get("transport") or "http") == "http"
        port = int(self.config.get("port") or (443 if http else 10000))
        try:
            check_host(self.config["host"], port)
        except BlockedAddress as exc:
            raise ConnectorError(str(exc)) from exc
        try:
            return connect(
                host=self.config["host"], port=port, user=self.config["username"],
                password=self.secrets.get("password", ""), auth_mechanism="LDAP", use_ssl=True,
                use_http_transport=http, http_path=self.config.get("http_path") or "cliservice",
                timeout=_timeout(),
            )
        except Exception as exc:  # noqa: BLE001  (thrift and impyla raise many kinds)
            raise ConnectorError(f"Could not connect: {str(exc).strip().splitlines()[0] if str(exc) else exc}") \
                from exc

    def _query(self, statement):
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(statement)
            names = [d[0].split(".")[-1] for d in cursor.description or []]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        except ConnectorError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(f"Cloudera: {str(exc).strip().splitlines()[0]}") from exc
        finally:
            conn.close()

    def _db(self):
        db = self.config["database"].strip()
        if not _IDENT.match(db):
            raise ConnectorError("Database names use letters, numbers and _ only.")
        return db

    def _split(self, obj):
        db, table = _three_part(obj, 2, "default.customers")
        if not (_IDENT.match(db) and _IDENT.match(table)):
            raise ConnectorError("Table names use letters, numbers and _ only.")
        return db, table

    def list_objects(self):
        db = self._db()
        return [f"{db}.{list(r.values())[-1]}" for r in self._query(f"SHOW TABLES IN `{db}`")]

    def list_columns(self, obj):
        db, table = self._split(obj)
        columns = []
        for row in self._query(f"DESCRIBE `{db}`.`{table}`"):
            name = str(list(row.values())[0] or "").strip()
            if not name or name.startswith("#"):
                break  # partition and detail sections follow a blank line
            columns.append(name)
        if not columns:
            raise ConnectorError(f"No table {obj}, or no permission to read it.")
        return columns

    def fetch(self, obj, columns, limit):
        db, table = self._split(obj)
        _checked(columns, self.list_columns(obj))
        quoted = ", ".join("`" + c.replace("`", "``") + "`" for c in columns)
        rows = self._query(f"SELECT {quoted} FROM `{db}`.`{table}` LIMIT {int(limit)}")
        return [{c: _plain(r.get(c)) for c in columns} for r in rows]
