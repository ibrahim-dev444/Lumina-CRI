from datetime import date, datetime, time

from django.conf import settings

from ..clean import clean_date
from .base import BaseConnector
from .catalog import adapter_for

IDENTITY_FIELDS = ("pan", "aadhaar", "ckyc")


class MappedConnector(BaseConnector):
    """A connector set up from the catalog: it reads the object and columns its mapping names, and renames them
    to Lumina's fields. Cleaning, encryption and matching then happen exactly as for the built-in connectors."""

    def __init__(self, source):
        self.source = source
        self.mapping = source.mapping or {}
        self.fields = self.mapping.get("fields") or {}
        self.id_column = self.mapping.get("id_column")
        self.updated_column = self.mapping.get("updated_column") or ""
        if not self.mapping.get("object") or not self.id_column or not self.fields.get("name"):
            from .adapters import ConnectorError

            raise ConnectorError("Finish the field mapping first (table, record ID and at least the name).")
        self.source_code = source.code
        self.sensitive_columns = {self.fields[f]: f for f in IDENTITY_FIELDS if self.fields.get(f)}

    def columns(self):
        wanted = [self.id_column, *self.fields.values()]
        if self.updated_column:
            wanted.append(self.updated_column)
        return list(dict.fromkeys(c for c in wanted if c))  # each column once, order kept

    def fetch(self):
        return adapter_for(self.source).fetch(self.mapping["object"], self.columns(), settings.CONNECTOR_MAX_ROWS)

    def record_id(self, raw):
        value = raw.get(self.id_column)
        return str(value).strip() if value not in (None, "") else ""

    def to_standard(self, raw):
        std = {field: raw.get(column) for field, column in self.fields.items()}
        std["source_updated_at"] = _when(raw.get(self.updated_column)) if self.updated_column else None
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
