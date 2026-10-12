"""The connector catalog: every kind of system an organization can connect, and the form each one needs.

Every organization sees the whole catalog and connects with its own details. Fields marked secret (passwords,
tokens, connection strings) are stored encrypted and never sent back to the browser.
"""

import json

from security import crypto

from .adapters import FileUploadAdapter, MongoAdapter, MySQLAdapter, PostgresAdapter, RestApiAdapter


def field(name, label, kind="text", required=True, secret=False, default="", help="", choices=None):
    return {
        "name": name,
        "label": label,
        "kind": kind,  # text, number, password, select
        "required": required,
        "secret": secret,
        "default": default,
        "help": help,
        "choices": choices or [],
    }


CATALOG = [
    {
        "type": "postgresql",
        "label": "PostgreSQL",
        "category": "Database",
        "description": "Read a customer table or view from a PostgreSQL database.",
        "object_label": "Table or view",
        "available": True,
        "fields": [
            field("host", "Server address", help="e.g. db.yourbank.com"),
            field("port", "Port", "number", default="5432"),
            field("database", "Database name"),
            field("username", "Username", help="A read-only user that can see only the customer table or view."),
            field("password", "Password", "password", secret=True),
            field("sslmode", "Encryption (SSL)", "select", default="require",
                  choices=[["require", "Required"], ["verify-full", "Required and verified"], ["prefer", "If available"]]),
        ],
        "adapter": PostgresAdapter,
    },
    {
        "type": "mysql",
        "label": "MySQL",
        "category": "Database",
        "description": "Read a customer table from a MySQL or MySQL-compatible database (TiDB, MariaDB).",
        "object_label": "Table",
        "available": True,
        "fields": [
            field("host", "Server address"),
            field("port", "Port", "number", default="3306"),
            field("database", "Database name"),
            field("username", "Username", help="A read-only user."),
            field("password", "Password", "password", secret=True),
            field("tls", "Encryption (TLS)", "select", default="true", choices=[["true", "On"], ["false", "Off"]]),
        ],
        "adapter": MySQLAdapter,
    },
    {
        "type": "mongodb",
        "label": "MongoDB",
        "category": "Database",
        "description": "Read customer documents from a MongoDB collection (for example MongoDB Atlas).",
        "object_label": "Collection",
        "available": True,
        "fields": [
            field("connection_string", "Connection string", "password", secret=True,
                  help="mongodb+srv://user:password@cluster.example.net"),
            field("database", "Database name"),
        ],
        "adapter": MongoAdapter,
    },
    {
        "type": "rest_api",
        "label": "REST API",
        "category": "API",
        "description": "Call a JSON API that lists customers, with an API key or bearer token.",
        "object_label": "Records",
        "available": True,
        "fields": [
            field("url", "API address", help="https://api.yourbank.com/v1/customers"),
            field("records_path", "Records path", required=False, help="Where the list is in the answer, e.g. data.customers. Empty if the answer is the list."),
            field("auth", "Sign-in method", "select", default="bearer",
                  choices=[["bearer", "Bearer token"], ["header", "API key header"], ["none", "None"]]),
            field("header_name", "API key header name", required=False, default="X-API-Key"),
            field("token", "Token or API key", "password", required=False, secret=True),
            field("page_param", "Page parameter", required=False, help="e.g. page. Empty if the API is not paged."),
            field("page_size_param", "Page size parameter", required=False, help="e.g. per_page"),
            field("page_size", "Page size", "number", required=False, default="100"),
        ],
        "adapter": RestApiAdapter,
    },
    {
        "type": "file_upload",
        "label": "File upload (CSV)",
        "category": "Files",
        "description": "Upload a CSV export, for example a branch spreadsheet saved as CSV.",
        "object_label": "File",
        "available": True,
        "fields": [],
        "adapter": FileUploadAdapter,
    },
    {
        "type": "salesforce",
        "label": "Salesforce",
        "category": "CRM",
        "description": "Read Contacts from Salesforce with an approved connected app.",
        "object_label": "Object",
        "available": False,  # comes with the real Salesforce sign-in
        "fields": [],
        "adapter": None,
    },
]

BY_TYPE = {entry["type"]: entry for entry in CATALOG}

# The built-in demo sources use hand-written connectors (ingestion/connectors/flexcube.py, ...).
DEMO_TYPES = {
    "demo_core_banking": "Demo core banking",
    "demo_salesforce": "Demo Salesforce export",
    "demo_branch_files": "Demo branch files",
}


def public_catalog():
    """The catalog as the browser sees it: no adapter classes."""
    return [{k: v for k, v in entry.items() if k != "adapter"} for entry in CATALOG]


def type_label(connector_type):
    if connector_type in BY_TYPE:
        return BY_TYPE[connector_type]["label"]
    return DEMO_TYPES.get(connector_type, connector_type or "Built-in")


def split_settings(connector_type, values):
    """Separate a submitted form into (config, secrets) using the catalog's field list."""
    entry = BY_TYPE[connector_type]
    config, secrets = {}, {}
    for f in entry["fields"]:
        if f["name"] not in values:
            continue
        value = values[f["name"]]
        value = "" if value is None else str(value).strip()
        (secrets if f["secret"] else config)[f["name"]] = value
    return config, secrets


def read_secrets(source):
    return json.loads(crypto.decrypt(source.secret)) if source.secret else {}


def write_secrets(source, secrets):
    """Merge new secrets into the stored ones. An empty value keeps what is stored (the form never shows it)."""
    current = read_secrets(source)
    current.update({k: v for k, v in secrets.items() if v})
    source.secret = crypto.encrypt(json.dumps(current)) if current else ""


def adapter_for(source):
    entry = BY_TYPE.get(source.connector_type)
    if entry is None or entry["adapter"] is None:
        from .adapters import ConnectorError

        raise ConnectorError(f"{type_label(source.connector_type)} cannot be set up here yet.")
    return entry["adapter"](source.config, read_secrets(source), source)
