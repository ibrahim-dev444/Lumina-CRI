"""How Lumina talks to each kind of system. Every adapter does the same four things:

  test()                     can we connect with these details?
  list_objects()             tables, views or collections we could read customers from
  list_columns(obj)          the columns (fields) of one of them
  fetch(obj, columns, limit) rows with ONLY those columns, read-only

Safety rules shared by all adapters: the server address must be on the public internet (security.network),
sessions are read-only where the database supports it, queries time out, rows are capped, and only column
names that list_columns() returned are ever put into a query.
"""

import csv
import io
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings

from security.network import BlockedAddress, check_host


class ConnectorError(ValueError):
    """A problem the administrator can fix: wrong password, unknown table, unreachable server..."""


def _timeout():
    return settings.CONNECTOR_TIMEOUT_SECONDS


def _plain(value):
    """Values from other systems turned into things JSON and our cleaners understand."""
    if value is None or isinstance(value, (str, int, float, bool, date, datetime)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)  # ObjectId, Decimal128, UUID ...


def _require(config, *keys):
    missing = [k for k in keys if not str(config.get(k) or "").strip()]
    if missing:
        raise ConnectorError(f"Missing: {', '.join(missing)}.")


def _checked(columns, known):
    unknown = [c for c in columns if c not in known]
    if unknown:
        raise ConnectorError(f"Unknown column(s): {', '.join(unknown)}. Run Discover again.")
    return columns


class BaseAdapter:
    def __init__(self, config, secrets, source=None):
        self.config = config or {}
        self.secrets = secrets or {}
        self.source = source

    def test(self):
        objects = self.list_objects()
        return f"Connected. Found {len(objects)} place(s) to read from."

    def list_objects(self):
        raise NotImplementedError

    def list_columns(self, obj):
        raise NotImplementedError

    def fetch(self, obj, columns, limit):
        raise NotImplementedError


# ---------- PostgreSQL ----------

class PostgresAdapter(BaseAdapter):
    def _connect(self):
        import psycopg

        _require(self.config, "host", "database", "username")
        port = int(self.config.get("port") or 5432)
        try:
            address = check_host(self.config["host"], port)
        except BlockedAddress as exc:
            raise ConnectorError(str(exc)) from exc
        try:
            return psycopg.connect(
                host=self.config["host"],
                hostaddr=address,  # connect to the address we checked, not a second lookup
                port=port,
                dbname=self.config["database"],
                user=self.config["username"],
                password=self.secrets.get("password", ""),
                sslmode=self.config.get("sslmode") or "require",
                connect_timeout=8,
                options=f"-c default_transaction_read_only=on -c statement_timeout={_timeout() * 1000}",
            )
        except psycopg.Error as exc:
            raise ConnectorError(f"Could not connect: {str(exc).strip().splitlines()[0]}") from exc

    def list_objects(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT table_schema || '.' || table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
                "AND table_type IN ('BASE TABLE', 'VIEW') ORDER BY 1 LIMIT 500"
            ).fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def _split(obj):
        if "." not in (obj or ""):
            raise ConnectorError("Choose a table, like public.customers.")
        return obj.split(".", 1)

    def list_columns(self, obj):
        schema, table = self._split(obj)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s "
                "ORDER BY ordinal_position",
                [schema, table],
            ).fetchall()
        if not rows:
            raise ConnectorError(f"No table {obj}, or no permission to read it.")
        return [r[0] for r in rows]

    def fetch(self, obj, columns, limit):
        from psycopg import sql
        from psycopg.rows import dict_row

        schema, table = self._split(obj)
        _checked(columns, self.list_columns(obj))
        query = sql.SQL("SELECT {} FROM {}.{} LIMIT {}").format(
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.Literal(limit),
        )
        with self._connect() as conn:
            conn.row_factory = dict_row
            return [{k: _plain(v) for k, v in row.items()} for row in conn.execute(query).fetchall()]


# ---------- MySQL ----------

class MySQLAdapter(BaseAdapter):
    def _connect(self):
        import pymysql

        _require(self.config, "host", "database", "username")
        port = int(self.config.get("port") or 3306)
        try:
            check_host(self.config["host"], port)
        except BlockedAddress as exc:
            raise ConnectorError(str(exc)) from exc
        use_tls = str(self.config.get("tls", "true")).lower() != "false"
        try:
            conn = pymysql.connect(
                host=self.config["host"],
                port=port,
                user=self.config["username"],
                password=self.secrets.get("password", ""),
                database=self.config["database"],
                connect_timeout=8,
                read_timeout=_timeout(),
                ssl=ssl.create_default_context() if use_tls else None,
                cursorclass=pymysql.cursors.DictCursor,
            )
        except pymysql.MySQLError as exc:
            raise ConnectorError(f"Could not connect: {exc.args[-1] if exc.args else exc}") from exc
        try:
            with conn.cursor() as cur:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
        except pymysql.MySQLError:
            pass  # some MySQL-compatible servers (e.g. TiDB) do not support it; the login itself is read-only
        return conn

    def list_objects(self):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name AS t FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY 1"
                )
                return [r["t"] for r in cur.fetchall()]
        finally:
            conn.close()

    def list_columns(self, obj):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name AS c FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position",
                    [obj],
                )
                columns = [r["c"] for r in cur.fetchall()]
        finally:
            conn.close()
        if not columns:
            raise ConnectorError(f"No table {obj}, or no permission to read it.")
        return columns

    def fetch(self, obj, columns, limit):
        _checked(columns, self.list_columns(obj))

        def quote(name):
            return "`" + name.replace("`", "``") + "`"

        query = f"SELECT {', '.join(quote(c) for c in columns)} FROM {quote(obj)} LIMIT %s"
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(query, [int(limit)])
                return [{k: _plain(v) for k, v in row.items()} for row in cur.fetchall()]
        finally:
            conn.close()


# ---------- MongoDB ----------

def _flatten(doc, prefix="", depth=0):
    """{"name": {"first": "A"}} -> {"name.first": "A"} (one level deep is enough for customer records)."""
    out = {}
    for key, value in doc.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and depth < 1:
            out.update(_flatten(value, path + ".", depth + 1))
        else:
            out[path] = value
    return out


class MongoAdapter(BaseAdapter):
    def _client(self):
        import pymongo
        from pymongo import uri_parser
        from pymongo.errors import ConfigurationError, InvalidURI

        uri = self.secrets.get("connection_string", "")
        _require(self.config, "database")
        if not uri.startswith(("mongodb://", "mongodb+srv://")):
            raise ConnectorError("The connection string must start with mongodb:// or mongodb+srv://.")
        try:
            hosts = uri_parser.parse_uri(uri)["nodelist"]
        except (ConfigurationError, InvalidURI, ValueError) as exc:
            raise ConnectorError(f"The connection string is not valid: {exc}") from exc
        for host, port in hosts:
            try:
                check_host(host, port)
            except BlockedAddress as exc:
                raise ConnectorError(str(exc)) from exc
        return pymongo.MongoClient(
            uri, serverSelectionTimeoutMS=8000, socketTimeoutMS=_timeout() * 1000, readPreference="secondaryPreferred"
        )

    def _run(self, work):
        from pymongo.errors import PyMongoError

        client = self._client()
        try:
            return work(client[self.config["database"]])
        except PyMongoError as exc:
            raise ConnectorError(f"MongoDB said: {str(exc).splitlines()[0][:200]}") from exc
        finally:
            client.close()

    def list_objects(self):
        return self._run(lambda db: sorted(db.list_collection_names()))

    def list_columns(self, obj):
        def columns(db):
            seen = []
            for doc in db[obj].find({}).limit(100):
                for key in _flatten(doc):
                    if key not in seen:
                        seen.append(key)
            return seen

        found = self._run(columns)
        if not found:
            raise ConnectorError(f"The collection {obj} is empty or does not exist.")
        return found

    def fetch(self, obj, columns, limit):
        _checked(columns, self.list_columns(obj))

        def rows(db):
            projection = {c: 1 for c in columns}
            if "_id" not in columns:
                projection["_id"] = 0
            out = []
            for doc in db[obj].find({}, projection).limit(int(limit)):
                flat = _flatten(doc)
                out.append({c: _plain(flat.get(c)) for c in columns})
            return out

        return self._run(rows)


# ---------- REST API ----------

class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect could send the request to an internal address after our check, so redirects are refused."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConnectorError(f"The API redirected to {newurl}. Use the final address instead.")


class RestApiAdapter(BaseAdapter):
    MAX_BYTES = 10 * 1024 * 1024
    MAX_PAGES = 200

    def _get(self, params=None):
        _require(self.config, "url")
        url = self.config["url"].strip()
        parts = urllib.parse.urlparse(url)
        if parts.scheme != "https" and not settings.CONNECTORS_ALLOW_PRIVATE_HOSTS:
            raise ConnectorError("Use an https:// address.")
        if parts.scheme not in ("http", "https"):
            raise ConnectorError("The address must start with https://.")
        try:
            check_host(parts.hostname, parts.port)
        except BlockedAddress as exc:
            raise ConnectorError(str(exc)) from exc
        if params:
            joiner = "&" if parts.query else "?"
            url = url + joiner + urllib.parse.urlencode(params)
        headers = {"Accept": "application/json", "User-Agent": "Lumina-CRI-connector"}
        token = self.secrets.get("token", "")
        auth = self.config.get("auth") or "none"
        if auth == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"
        elif auth == "header" and token:
            headers[self.config.get("header_name") or "X-API-Key"] = token
        opener = urllib.request.build_opener(_NoRedirects)
        try:
            with opener.open(urllib.request.Request(url, headers=headers), timeout=_timeout()) as response:
                body = response.read(self.MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise ConnectorError(f"The API answered {exc.code} {exc.reason}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ConnectorError(f"Could not reach the API: {getattr(exc, 'reason', exc)}") from exc
        if len(body) > self.MAX_BYTES:
            raise ConnectorError("The API answer is larger than 10 MB. Use paging.")
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise ConnectorError("The API did not answer with JSON.") from exc
        for key in [k for k in (self.config.get("records_path") or "").split(".") if k]:
            data = data.get(key) if isinstance(data, dict) else None
        if not isinstance(data, list):
            raise ConnectorError("Could not find a list of records. Check the records path (e.g. data.customers).")
        return [_flatten(r) for r in data if isinstance(r, dict)]

    def _page(self, number):
        page_param = (self.config.get("page_param") or "").strip()
        if not page_param:
            return self._get()
        params = {page_param: number}
        size_param = (self.config.get("page_size_param") or "").strip()
        if size_param:
            params[size_param] = int(self.config.get("page_size") or 100)
        return self._get(params)

    def list_objects(self):
        return ["records"]

    def list_columns(self, obj):
        seen = []
        for record in self._page(1)[:100]:
            for key in record:
                if key not in seen:
                    seen.append(key)
        if not seen:
            raise ConnectorError("The API returned no records to look at.")
        return seen

    def fetch(self, obj, columns, limit):
        _checked(columns, self.list_columns(obj))
        rows = []
        paged = bool((self.config.get("page_param") or "").strip())
        for number in range(1, self.MAX_PAGES + 1):
            page = self._page(number)
            rows.extend({c: _plain(r.get(c)) for c in columns} for r in page)
            if not paged or not page or len(rows) >= limit:
                break
        return rows[:limit]


# ---------- File upload (CSV) ----------

FILE_KEY = "_lumina_file"  # added to each row read from an uploaded file: which file it came from
FILES_OBJECT = "Uploaded files"


class FileUploadAdapter(BaseAdapter):
    """Reads every active CSV uploaded to the connector. Columns come from the newest active file; uploads are
    checked against the mapping, so every active file has the mapped columns."""

    def _active(self):
        files = list(self.source.uploads.filter(status="active")) if self.source is not None and self.source.pk             else []
        if not files:
            raise ConnectorError("Upload a CSV file first, or resume a suspended one.")
        return files  # newest first

    def test(self):
        files = self._active()
        rows = sum(f.rows for f in files)
        return f"{len(files)} active file{'s' if len(files) != 1 else ''}, {rows} rows."

    def list_objects(self):
        self._active()
        return [FILES_OBJECT]

    def list_columns(self, obj=None):
        return csv_header(self._active()[0].content)

    def fetch(self, obj, columns, limit):
        _checked(columns, self.list_columns(obj))
        id_column = (self.source.mapping or {}).get("id_column") or columns[0]
        by_id, without_id = {}, []
        for upload in reversed(self._active()):  # oldest first, so a newer file overwrites the same customer ID
            for row in csv.DictReader(io.StringIO(upload.content)):
                clean = {(k or "").strip(): v for k, v in row.items()}
                picked = {**{c: clean.get(c) for c in columns}, FILE_KEY: upload.id}
                key = (clean.get(id_column) or "").strip()
                if key:
                    by_id[key] = picked
                else:
                    without_id.append(picked)  # counted as read; the sync skips rows without an ID
        return (list(by_id.values()) + without_id)[:limit]


def csv_header(text):
    header = next(csv.reader(io.StringIO(text)), [])
    if not header:
        raise ConnectorError("The file has no header row.")
    return [h.strip() for h in header]


def parse_csv_upload(name, raw_bytes):
    """Check an uploaded CSV and return (text, row_count). Excel's invisible start marker is removed."""
    if len(raw_bytes) > 5 * 1024 * 1024:
        raise ConnectorError("The file must be 5 MB or smaller.")
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ConnectorError("Save the file as CSV (UTF-8) and upload it again.") from exc
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or not any(h.strip() for h in header):
        raise ConnectorError("The file has no header row.")
    rows = sum(1 for row in reader if any(cell.strip() for cell in row))
    if rows == 0:
        raise ConnectorError("The file has a header but no rows.")
    return text, rows
