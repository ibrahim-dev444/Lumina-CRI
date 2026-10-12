import hmac

from django.conf import settings
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ingestion.schedule import run_due_syncs


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def run_scheduled_syncs(request):
    """POST /api/internal/run-due-syncs/  with header X-Sync-Token: <SYNC_RUNNER_TOKEN>.
    Called hourly by the scheduler. Answers with counts only."""
    expected = settings.SYNC_RUNNER_TOKEN
    given = request.headers.get("X-Sync-Token", "")
    if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
        return Response({"detail": "Not allowed."}, status=403)
    return Response(run_due_syncs())
