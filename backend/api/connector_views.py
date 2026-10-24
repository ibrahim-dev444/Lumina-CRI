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
from ingestion.connectors.adapters import ConnectorError
from ingestion.connectors.catalog import BY_TYPE, adapter_for, public_catalog, split_settings, write_secrets
from ingestion.files import refresh, remove_files, removal_plan, set_status, upload_files
from ingestion.retire import plan, remove_sources
from ingestion.tables import remove_tables, save_table, set_table_status
from ingestion.tables import removal_plan as table_removal_plan
from mdm.field_trust import get_field_trust, set_field_trust
from mdm.models import FIELDS
from mdm.trust_settings import TrustSettingsError
from products.services import ACCOUNT_FIELDS
from security import crypto
from sources.models import Source

from .permissions import HasRole, requires
from .serializers import SourceSerializer

ADMIN_ONLY = [HasRole, requires("manage_connectors")]


def _source_json(source):
    source.record_count = source.records.filter(active=True).count()
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


@api_view(["GET", "PUT"])
@permission_classes([HasRole])
def field_trust(request, code):
    """GET /api/connectors/<code>/trust/  every field this connector supplies and how much it is trusted for it.
    PUT {trust: {field: 0-100}}  administrators only; recalculates every customer."""
    source = Source.objects.filter(code=code).first()
    if source is None:
        return Response({"detail": "No such connector."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "PUT":
        if not requires("manage_settings")().has_permission(request, None):
            return Response({"detail": "Only an administrator can change trust."}, status=status.HTTP_403_FORBIDDEN)
        try:
            changes = set_field_trust(source, request.data.get("trust"))
        except TrustSettingsError as exc:
            return _bad(exc)
        if changes:
            record(request, AuditEvent.SETTINGS_CHANGED, target=f"source {code} trust", changes=changes)
    return Response(get_field_trust(source))


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
    kept = {k: v for k, v in (source.mapping or {}).items() if k in ("accounts", "tables", "status") and v}
    source.mapping = {"object": obj, "id_column": id_column, "updated_column": updated_column, "fields": fields,
                      **kept}  # the accounts table and added customer tables are saved on their own
    source.save(update_fields=["mapping"])
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", mapping=source.mapping)
    return Response(_source_json(source))


@api_view(["GET", "POST"])
@permission_classes(ADMIN_ONLY)
def delete_connector(request, code):
    """GET  /api/connectors/<code>/delete/  what deleting would remove (counts only)
    POST /api/connectors/<code>/delete/  {confirm: "<the connector's name>"}  deletes it for good.
    Removes everything read from it and the customers no other system describes. Cannot be undone; the audit
    log keeps a record of who deleted what."""
    source = Source.objects.filter(code=code).first()
    if source is None:
        return Response({"detail": "No such connector."}, status=status.HTTP_404_NOT_FOUND)
    impact = plan([source])
    counts = {"records": impact.records, "products": impact.products, "customers": impact.customers_removed,
              "conversations": impact.conversations_removed, "corrections": impact.corrections_removed}
    if request.method == "GET":
        return Response({"name": source.name, **counts})
    if str(request.data.get("confirm", "")).strip() != source.name:
        return _bad(f"Type the connector's name exactly ({source.name}) to delete it.")
    name = source.name
    remove_sources([source])
    record(request, AuditEvent.CONNECTOR_DELETED, target=f"source {code}", name=name, **counts)
    return Response({"deleted": code, **counts})


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
    """POST /api/connectors/<code>/upload/  multipart "files" (up to 20 CSVs, 5 MB each; "file" also works).
    Each file is checked on its own; good files are kept even when others are refused. Then the connector is
    re-read, if its columns are already mapped."""
    source, error = _configurable(code)
    if error:
        return error
    if source.connector_type != "file_upload":
        return _bad("Only file-upload connectors take files.")
    uploads = request.FILES.getlist("files") or request.FILES.getlist("file")
    try:
        results = upload_files(source, uploads, request.user.get_username())
    except ConnectorError as exc:
        return _bad(exc)
    saved = [r for r in results if r["ok"]]
    if saved:
        record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}",
               uploaded=[r["name"] for r in saved], rows=sum(r["rows"] for r in saved))
        _refresh_or_report(source, request)
    first = saved[0] if saved else {}
    return Response({"files": results, "name": first.get("name"), "rows": first.get("rows")},
                     status=status.HTTP_200_OK if saved else status.HTTP_400_BAD_REQUEST)


def _refresh_or_report(source, request):
    try:
        refresh(source, request.user.get_username())
    except (ConnectorError, ValueError):
        pass  # the sync history records what went wrong; the files themselves are saved


def _file_json(f):
    return {"id": f.id, "name": f.name, "rows": f.rows, "status": f.status,
            "uploaded_at": f.uploaded_at.isoformat(), "uploaded_by": f.uploaded_by}


def _file_source(code):
    source = Source.objects.filter(code=code, connector_type="file_upload").first()
    if source is None:
        return None, Response({"detail": "No such file-upload connector."}, status=status.HTTP_404_NOT_FOUND)
    return source, None


def _ids(request):
    raw = request.data.get("ids") if request.method == "POST" else request.query_params.get("ids", "")
    if isinstance(raw, str):
        raw = raw.split(",")
    return [int(i) for i in raw or [] if str(i).strip().isdigit()]


MULTI_TABLE_TYPES = {"postgresql", "mysql", "mongodb", "snowflake", "databricks", "servicenow", "salesforce",
                     "cloudera"}


def _table_source(code):
    source, error = _configurable(code)
    if error:
        return None, error
    if source.connector_type not in MULTI_TABLE_TYPES:
        return None, _bad("This kind of connector reads one place only.")
    return source, None


def _keys(request):
    raw = request.data.get("keys") if request.method == "POST" else request.query_params.get("keys", "")
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(k).strip() for k in raw or [] if str(k).strip()]


@api_view(["PUT"])
@permission_classes(ADMIN_ONLY)
def save_customer_table(request, code):
    """PUT /api/connectors/<code>/tables/  {key?, object, id_column, updated_column?, fields}
    Adds another customer table (no key) or changes an added one. Checked against the live columns."""
    source, error = _table_source(code)
    if error:
        return error
    key = str(request.data.get("key") or "").strip() or None
    try:
        key = save_table(source, request.data, key)
    except ConnectorError as exc:
        return _bad(exc)
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", table=key,
           object=str(request.data.get("object", ""))[:100])
    return Response({"key": key, **_source_json(source)})


@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
def table_status(request, code):
    """POST /api/connectors/<code>/tables/status/  {keys: ["main", "t2"], status: "active" | "suspended"}"""
    source, error = _table_source(code)
    if error:
        return error
    keys, wanted = _keys(request), request.data.get("status")
    if not keys:
        return _bad("Choose one or more tables.")
    try:
        changed = set_table_status(source, keys, wanted, request.user.get_username())
    except (ConnectorError, ValueError) as exc:
        return _bad(exc)
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", tables=keys, status=wanted)
    return Response({"changed": changed, **_source_json(source)})


@api_view(["GET", "POST"])
@permission_classes(ADMIN_ONLY)
def remove_tables_view(request, code):
    """GET  /api/connectors/<code>/tables/remove/?keys=t2  what removing those tables would remove (counts)
    POST /api/connectors/<code>/tables/remove/  {keys: [..], confirm: true}  removes them for good."""
    source, error = _table_source(code)
    if error:
        return error
    keys = _keys(request)
    if not keys:
        return _bad("Choose one or more tables.")
    try:
        if request.method == "GET":
            return Response(table_removal_plan(source, keys).__dict__)
        if request.data.get("confirm") is not True:
            return _bad("Confirm the removal.")
        plan = remove_tables(source, keys, request.user.get_username())
    except (ConnectorError, ValueError) as exc:
        return _bad(exc)
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", removed_tables=keys, **plan.__dict__)
    return Response({**plan.__dict__, **_source_json(source)})


@api_view(["GET"])
@permission_classes(ADMIN_ONLY)
def list_files(request, code):
    """GET /api/connectors/<code>/files/  Every file uploaded to this connector, newest first."""
    source, error = _file_source(code)
    if error:
        return error
    return Response([_file_json(f) for f in source.uploads.all()])


@api_view(["POST"])
@permission_classes(ADMIN_ONLY)
def file_status(request, code):
    """POST /api/connectors/<code>/files/status/  {ids: [..], status: "active" | "suspended"}
    Suspending hides the customers only those files hold; resuming brings them back with the same IDs."""
    source, error = _file_source(code)
    if error:
        return error
    ids, wanted = _ids(request), request.data.get("status")
    if not ids:
        return _bad("Choose one or more files.")
    try:
        changed = set_status(source, ids, wanted, request.user.get_username())
    except (ConnectorError, ValueError) as exc:
        return _bad(exc)
    names = list(source.uploads.filter(id__in=ids).values_list("name", flat=True))
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", files=names, status=wanted)
    return Response({"changed": changed, "files": [_file_json(f) for f in source.uploads.all()]})


@api_view(["GET", "POST"])
@permission_classes(ADMIN_ONLY)
def remove_files_view(request, code):
    """GET  /api/connectors/<code>/files/remove/?ids=1,2  what removing those files would remove (counts only)
    POST /api/connectors/<code>/files/remove/  {ids: [..], confirm: true}  removes them for good."""
    source, error = _file_source(code)
    if error:
        return error
    ids = _ids(request)
    if not ids:
        return _bad("Choose one or more files.")
    if request.method == "GET":
        return Response(removal_plan(source, ids).__dict__)
    if request.data.get("confirm") is not True:
        return _bad("Confirm the removal.")
    names = list(source.uploads.filter(id__in=ids).values_list("name", flat=True))
    try:
        plan = remove_files(source, ids, request.user.get_username())
    except (ConnectorError, ValueError) as exc:
        return _bad(exc)
    record(request, AuditEvent.CONNECTOR_CHANGED, target=f"source {code}", removed_files=names, **plan.__dict__)
    return Response({**plan.__dict__, "files": [_file_json(f) for f in source.uploads.all()]})


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
