"""The push API: a bank's own system sends customers to Lumina.

    POST /t/<org>/api/ingest/<connector code>/
    Authorization: Bearer lum_...
    {"records": [{"id": "C-1", "name": "Asha Rao", "mobile": "9000000001", "pan": "ABCPR1234K",
                  "updated_at": "2026-10-01T10:00:00"}]}

Authentication is the connector's API key only (no sign-in session), so it is checked here and nowhere else.
Records go through the same raw copy, cleaning, encryption, matching and scoring as every other source.
"""

import hmac
import json

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from audit.models import AuditEvent
from audit.services import record
from ingestion.connectors.push import PUSH_FIELDS
from ingestion.sync import ingest_records
from mdm.services import build_customers
from security import crypto
from sources.models import Source

from .connector_views import hash_api_key
from .throttles import IngestThrottle

MAX_RECORDS = 1000
ALLOWED_KEYS = set(PUSH_FIELDS) | {"id", "updated_at"}


def _key_matches(source, given):
    if not source.secret or not given.startswith("lum_"):
        return False
    stored = json.loads(crypto.decrypt(source.secret)).get("key_hash", "")
    return bool(stored) and hmac.compare_digest(stored, hash_api_key(given))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([IngestThrottle])
def ingest(request, code):
    source = Source.objects.filter(code=code, connector_type="push_api").first()
    auth = request.headers.get("Authorization", "")
    given = auth[7:].strip() if auth.startswith("Bearer ") else ""
    # Same answer for "no such connector" and "wrong key", so keys and codes cannot be probed.
    if source is None or not _key_matches(source, given):
        return Response({"detail": "Invalid API key."}, status=status.HTTP_401_UNAUTHORIZED)
    if not source.enabled:
        return Response({"detail": "This connector is turned off."}, status=status.HTTP_403_FORBIDDEN)

    records = request.data.get("records") if isinstance(request.data, dict) else None
    if not isinstance(records, list) or not records:
        return Response({"detail": 'Send {"records": [...]} with at least one record.'}, status=400)
    if len(records) > MAX_RECORDS:
        return Response({"detail": f"At most {MAX_RECORDS} records per request."}, status=400)
    problems = []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            problems.append(f"record {i}: not an object")
            continue
        unknown = set(r) - ALLOWED_KEYS
        if unknown:
            problems.append(f"record {i}: unknown field(s) {', '.join(sorted(unknown))}")
        if not str(r.get("id") or "").strip() or not str(r.get("name") or "").strip():
            problems.append(f"record {i}: id and name are required")
    if problems:
        return Response({"detail": "Some records were not accepted.", "problems": problems[:20]}, status=400)

    prefix = source.config.get("key_prefix", "")
    with transaction.atomic():
        result = ingest_records(source, records, started_by=f"API key {prefix}")
        build_customers()
    record(request, AuditEvent.SYNC_SOURCE, target=f"source {code}", username=f"API key {prefix}",
           received=len(records), created=result.created, updated=result.updated)
    return Response({"received": len(records), "created": result.created, "updated": result.updated},
                    status=status.HTTP_202_ACCEPTED)
