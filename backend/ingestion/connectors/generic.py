import re
from datetime import date, datetime, time

from django.conf import settings

from ..clean import clean_date
from .base import BaseConnector
from .adapters import FILES_OBJECT
from .catalog import adapter_for

IDENTITY_FIELDS = ("pan", "aadhaar", "ckyc")
TABLE_KEY = "_lumina_table"  # added to each row: which of the connector's customer tables it came from
MAIN = "main"


def customer_tables(mapping):
    """Every customer table of a connector: the main one (the mapping's own keys) and any added later
    (mapping["tables"]). Each: {key, object, id_column, updated_column, fields, status}."""
    mapping = mapping or {}
    tables = []
    if mapping.get("object"):
        tables.append({"key": MAIN, "object": mapping["object"], "id_column": mapping.get("id_column"),
                       "updated_column": mapping.get("updated_column") or "", "fields": mapping.get("fields") or {},
                       "status": mapping.get("status") or "active"})
    for t in mapping.get("tables") or []:
        tables.append({"updated_column": "", "fields": {}, "status": "active", **t})
    return tables


def record_key(table_key, raw_id):
    """Rows from added tables carry their table's key, so the same ID in two tables stays two records. The main
    table keeps plain IDs, so existing records and the accounts table keep matching."""
    return raw_id if table_key == MAIN else f"{table_key}:{raw_id}"


class MappedConnector(BaseConnector):
    """A connector set up from the catalog: it reads the tables and columns its mapping names, and renames them
    to Lumina's fields. Cleaning, encryption and matching then happen exactly as for the built-in connectors."""

    def __init__(self, source):
        self.source = source
        self.mapping = source.mapping or {}
        self.tables = {t["key"]: t for t in customer_tables(self.mapping)}
        main = self.tables.get(MAIN)
        if not main or not main["id_column"] or not main["fields"].get("name"):
            from .adapters import ConnectorError

            raise ConnectorError("Finish the field mapping first (table, record ID and at least the name).")
        self.source_code = source.code
        self.sensitive_columns = {t["fields"][f]: f for t in self.tables.values() for f in IDENTITY_FIELDS
                                  if t["fields"].get(f)}

    @staticmethod
    def _columns(table):
        wanted = [table["id_column"], *table["fields"].values()]
        if table["updated_column"]:
            wanted.append(table["updated_column"])
        return list(dict.fromkeys(c for c in wanted if c))  # each column once, order kept

    def columns(self):
        return self._columns(self.tables[MAIN])

    def suspended_tables(self):
        return [k for k, t in self.tables.items() if t["status"] != "active"]

    def fetch(self):
        """Rows from every active table, each tagged with its table. Sets self.complete: False when a table hit the
        row limit, so the sync knows it may not have seen every row."""
        adapter, rows = adapter_for(self.source), []
        self.complete = True
        for key, table in self.tables.items():
            if table["status"] != "active":
                continue
            read = adapter.fetch(table["object"], self._columns(table), settings.CONNECTOR_MAX_ROWS)
            if len(read) >= settings.CONNECTOR_MAX_ROWS:
                self.complete = False
            rows.extend({**row, TABLE_KEY: key} for row in read)
        return rows

    def active_tables(self):
        return [k for k, t in self.tables.items() if t["status"] == "active"]

    def accounts_mapping(self):
        """How to read this connector's products: its accounts table, or for a CSV connector its optional Product
        column (one product per row, or several separated by ; or ,). None when neither is set up."""
        if self.mapping.get("accounts"):
            return self.mapping["accounts"]
        if self.source.connector_type == "file_upload" and self.mapping.get("product_column"):
            return {"id_column": "account", "customer_column": "customer", "fields": {"product_name": "product"},
                    "no_number": True}
        return None

    def fetch_accounts(self):
        """The rows of the optional accounts mapping (accounts, deposits, loans, cards), or None if not set up."""
        accounts = self.mapping.get("accounts")
        product_column = self.mapping.get("product_column")
        if not accounts and self.source.connector_type == "file_upload" and product_column:
            id_column = self.tables[MAIN]["id_column"]
            rows = []
            for raw in adapter_for(self.source).fetch(FILES_OBJECT, [id_column, product_column],
                                                      settings.CONNECTOR_MAX_ROWS):
                customer = str(raw.get(id_column) or "").strip()
                for product in re.split(r"[;,]", str(raw.get(product_column) or "")):
                    product = product.strip()
                    if customer and product:
                        rows.append({"account": f"{customer}|{product.lower()}", "customer": customer,
                                     "product": product})
            return rows
        if not accounts:
            return None
        wanted = [accounts["id_column"], accounts["customer_column"], *(accounts.get("fields") or {}).values()]
        if accounts.get("updated_column"):
            wanted.append(accounts["updated_column"])
        columns = list(dict.fromkeys(c for c in wanted if c))
        return adapter_for(self.source).fetch(accounts["object"], columns, settings.CONNECTOR_MAX_ROWS)

    def _table(self, raw):
        return self.tables.get(raw.get(TABLE_KEY) or MAIN) or self.tables[MAIN]

    def record_id(self, raw):
        table = self._table(raw)
        value = raw.get(table["id_column"])
        return record_key(table["key"], str(value).strip()) if value not in (None, "") else ""

    def to_standard(self, raw):
        table = self._table(raw)
        std = {field: raw.get(column) for field, column in table["fields"].items()}
        updated = table["updated_column"]
        std["source_updated_at"] = _when(raw.get(updated)) if updated else None
        return std


def _when(value):
    """A "last updated" value from any system, as a datetime (or None)."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            day = clean_date(text)
            return datetime.combine(day, time.min) if day else None
    return None
