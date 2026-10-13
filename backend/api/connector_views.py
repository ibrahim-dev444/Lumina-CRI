"""Setting up connectors (organization administrators only): pick a type from the catalog, enter the
connection details, test, discover tables and columns, map columns to Lumina's fields. Syncing stays on the
sources API (stewards and admins).

Passwords, tokens and connection strings are stored encrypted, never returned and never written to the
audit log.
"""

import hashlib
import json
import secrets
from decimal import Decimal

from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from audit.models import AuditEvent
from audit.services import record
from ingestion.connectors.adapters import ConnectorError, parse_csv_upload
from ingestion.connectors.catalog import BY_TYPE, adapter_for, public_catalog, split_settings, write_secrets
from mdm.models import FIELDS
from products.services import ACCOUNT_FIELDS
from security import crypto
from sources.models import Source, UploadedFile

from .permissions import HasRole, requires
from .serializers import SourceSerializer

ADMIN_ONLY = [HasRole, requires("manage_connectors")]


def _source_json(source):
    source.record_count = source.records.count()
    return SourceSerializer(source).data


def _configurable(code):
    source = Source.objects.filter(code=code).first()
    if source is None:
        return None, Response({"detail": "No such connector."}, status=status.HTTP_404_NOT_FOUND)
    if source.connector_type not in BY_TYPE:
        return None, Response(
            {"detail": "Built-in demo connectors cannot be reconfigured."}, status=status.HTTP_400_BAD_REQUEST
        )
    return source, None


def _bad(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([HasRole])
def catalog(request):
    """GET /api/connectors/catalog/  Every connector type and the form it needs. Same for every organization."""
    return Response(public_catalog())


@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
def create_connector(request):
    """POST /api/connectors/  {name, connector_type, category?, trust (0-100), settings: {...}}"""
    d = request.data
    connector_type = d.get("connector_type")
    entry = BY_TYPE.get(connector_type)
    if entry is None or not entry["available"]:
        return _bad("Choose an available connector type.")
    name = str(d.get("name") or "").strip()
    if not 2 <= len(name) <= 100:
        return _bad("Name: 2 to 100 characters, e.g. Core banking replica.")
    trust = d.get("trust", 50)
    if isinstance(trust, bool) or not isinstance(trust, int) or not 0 <= trust <= 100:
        return _bad("Trust must be a whole number from 0 to 100.")

    base = slugify(name)[:40] or connector_type
    code, n = base, 2
    while Source.objects.filter(code=code).exists():
        code, n = f"{base}-{n}", n + 1

    config, secrets = split_settings(connector_type, d.get("settings") or {})
    missing = [f["label"] for f in entry["fields"] if f["required"] and not (config.get(f["name"]) or secrets.get(f["name"]))]
    if missing:
        return _bad(f"Missing: {', '.join(missing)}.")

    source = Source(
        code=code, name=name, category=str(d.get("category") or entry["category"])[:50],
        trust=Decimal(trust) / 100, connector_type=connector_type, config=config, enabled=True,
    )
    write_secrets(source, secrets)
    source.save()
    record(request, AuditEvent.CONNECTOR_ADDED, target=f"source {code}", connector_type=connector_type, config=config)
    return Response(_source_json(source), status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(ADMIN_ONLY)
def update_connector(request, code):
    """PATCH /api/connectors/<code>/  {name?, settings?}  Empty secret fields keep the stored value."""
    source, error = _configurable(code)
    if error:
        return error
    changes = {}
    if "name" in request.data:
        name = str(request.data["name"]).strip()
        if not 2 <= len(name) <= 100:
            return _bad("Name: 2 to 100 characters.")
        changes["name"] = [source.name, name]
        source.name = name
    if "settings" in request.data:
        config, secrets = split_settings(source.connector_type, request.data["settings"] or {})
        changes["config"] = [source.config, {**source.config, **config}]
        source.config = {**source.config, **config}
        if any(secrets.values()):
            changes["secret"] = "replaced"  # never the value itself
        write_secrets(source, secrets)
    source.save()
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", changes=changes)
    return Response(_source_json(source))


@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
def test_connector(request, code):
    """POST /api/connectors/<code>/test/  Connects with the stored details and reports what it found."""
    source, error = _configurable(code)
    if error:
        return error
    try:
        message = adapter_for(source).test()
    except ConnectorError as exc:
        return Response({"ok": False, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"ok": True, "detail": message})


@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
def discover(request, code):
    """POST /api/connectors/<code>/discover/  {} lists tables or collections; {object} lists its columns."""
    source, error = _configurable(code)
    if error:
        return error
    try:
        adapter = adapter_for(source)
        obj = request.data.get("object")
        if obj:
            return Response({"object": obj, "columns": adapter.list_columns(obj)})
        return Response({"objects": adapter.list_objects()})
    except ConnectorError as exc:
        return _bad(exc)


@api_view(["PUT"])
@permission_classes(ADMIN_ONLY)
def save_mapping(request, code):
    """PUT /api/connectors/<code>/mapping/
    {object, id_column, updated_column?, fields: {lumina_field: source_column}}  Checked against the live columns."""
    source, error = _configurable(code)
    if error:
        return error
    d = request.data
    obj = str(d.get("object") or "").strip()
    fields = {k: v for k, v in (d.get("fields") or {}).items() if v}
    id_column = str(d.get("id_column") or "").strip()
    updated_column = str(d.get("updated_column") or "").strip()
    unknown_fields = [f for f in fields if f not in FIELDS]
    if unknown_fields:
        return _bad(f"Unknown Lumina field(s): {', '.join(unknown_fields)}.")
    if not obj or not id_column:
        return _bad("Choose what to read and which column is the record ID.")
    if not fields.get("name"):
        return _bad("Map at least the customer name.")
    try:
        columns = adapter_for(source).list_columns(obj)
    except ConnectorError as exc:
        return _bad(exc)
    used = [id_column, *fields.values()] + ([updated_column] if updated_column else [])
    missing = [c for c in used if c not in columns]
    if missing:
        return _bad(f"{', '.join(missing)} not found in {obj}.")
    accounts = (source.mapping or {}).get("accounts")  # the accounts mapping is saved on its own
    source.mapping = {"object": obj, "id_column": id_column, "updated_column": updated_column, "fields": fields}
    if accounts:
        source.mapping["accounts"] = accounts
    source.save(update_fields=["mapping"])
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", mapping=source.mapping)
    return Response(_source_json(source))


@api_view(["PUT", "DELETE"])
@permission_classes(ADMIN_ONLY)
def save_accounts_mapping(request, code):
    """PUT /api/connectors/<code>/accounts-mapping/
    {object, id_column, customer_column, updated_column?, fields: {account_field: source_column}}
    Optional second table with the customers' accounts, deposits, loans and cards. DELETE stops reading it."""
    source, error = _configurable(code)
    if error:
        return error
    if not source.mapping.get("object"):
        return _bad("Map the customers first.")
    mapping = dict(source.mapping)
    if request.method == "DELETE":
        mapping.pop("accounts", None)
        source.mapping = mapping
        source.save(update_fields=["mapping"])
        source.holdings.all().delete()
        record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", accounts_mapping=None)
        return Response(_source_json(source))

    d = request.data
    obj = str(d.get("object") or "").strip()
    id_column = str(d.get("id_column") or "").strip()
    customer_column = str(d.get("customer_column") or "").strip()
    updated_column = str(d.get("updated_column") or "").strip()
    fields = {k: v for k, v in (d.get("fields") or {}).items() if v}
    unknown = [f for f in fields if f not in ACCOUNT_FIELDS]
    if unknown:
        return _bad(f"Unknown account field(s): {', '.join(unknown)}.")
    if not obj or not id_column or not customer_column:
        return _bad("Choose the accounts table, its account number column and its customer ID column.")
    if not (fields.get("product_type") or fields.get("product_name")):
        return _bad("Map the product type or the product name, so Lumina knows what each account is.")
    try:
        columns = adapter_for(source).list_columns(obj)
    except ConnectorError as exc:
        return _bad(exc)
    used = [id_column, customer_column, *fields.values()] + ([updated_column] if updated_column else [])
    missing = [c for c in used if c not in columns]
    if missing:
        return _bad(f"{', '.join(missing)} not found in {obj}.")
    mapping["accounts"] = {"object": obj, "id_column": id_column, "customer_column": customer_column,
                           "updated_column": updated_column, "fields": fields}
    source.mapping = mapping
    source.save(update_fields=["mapping"])
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", accounts_mapping=mapping["accounts"])
    return Response(_source_json(source))


@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
@parser_classes([MultiPartParser])
def upload_file(request, code):
    """POST /api/connectors/<code>/upload/  multipart "file": a CSV for a file-upload connector."""
    source, error = _configurable(code)
    if error:
        return error
    if source.connector_type != "file_upload":
        return _bad("Only file-upload connectors take files.")
    upload = request.FILES.get("file")
    if upload is None:
        return _bad("Choose a CSV file.")
    try:
        text, rows = parse_csv_upload(upload.name, upload.read())
    except ConnectorError as exc:
        return _bad(exc)
    UploadedFile.objects.create(
        source=source, name=upload.name[:200], content=text, rows=rows, uploaded_by=request.user.get_username()
    )
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", uploaded=upload.name[:200], rows=rows)
    return Response({"name": upload.name, "rows": rows})


@api_view(["GET"])
@permission_classes([HasRole, requires("manage_sources", "manage_connectors")])
def sync_runs(request, code):
    """GET /api/connectors/<code>/runs/  The last 50 syncs of this source."""
    source = Source.objects.filter(code=code).first()
    if source is None:
        return Response({"detail": "No such connector."}, status=status.HTTP_404_NOT_FOUND)
    return Response([
        {"id": r.id, "status": r.status, "started_at": r.started_at.isoformat(),
         "finished_at": r.finished_at.isoformat() if r.finished_at else None,
         "fetched": r.fetched, "created": r.created, "updated": r.updated, "error": r.error,
         "started_by": r.started_by}
        for r in source.runs.all()[:50]
    ])


@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
def create_api_key(request, code):
    """POST /api/connectors/<code>/api-key/  A new key for a push-API connector. Shown once; only a one-way
    hash is stored, so a lost key cannot be recovered, only replaced. The old key stops working at once."""
    source, error = _configurable(code)
    if error:
        return error
    if source.connector_type != "push_api":
        return _bad("Only push-API connectors have API keys.")
    key = "lum_" + secrets.token_urlsafe(32)
    source.secret = crypto.encrypt(json.dumps({"key_hash": hash_api_key(key)}))
    source.config = {**source.config, "key_prefix": key[:12]}
    source.mapping = {"push": True}
    source.save(update_fields=["secret", "config", "mapping"])
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", api_key="replaced", prefix=key[:12])
    return Response({"api_key": key, "key_prefix": key[:12]})


def hash_api_key(key):
    return hashlib.sha256(key.encode()).hexdigest()
