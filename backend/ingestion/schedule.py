"""Scheduled syncs: every organization's sources that asked to sync every N hours, synced when due.

Called once an hour (GitHub Actions calls a protected endpoint; locally: python manage.py run_due_syncs).
Each organization runs inside its own schema; a failure in one source or organization does not stop the rest.
"""

from datetime import timedelta

from django.utils import timezone
from django_tenants.utils import schema_context

ALLOWED_INTERVALS = (0, 6, 12, 24)


def due_sources(now=None):
    """Sources in the current organization whose schedule says they should sync now."""
    from sources.models import Source

    now = now or timezone.now()
    due = []
    for source in Source.objects.filter(enabled=True, sync_every_hours__gt=0).exclude(connector_type="push_api"):
        if source.last_synced_at is None or source.last_synced_at <= now - timedelta(hours=source.sync_every_hours):
            due.append(source)
    return due


def run_due_syncs():
    """Sync everything that is due in every active organization. Returns counts only (no customer data)."""
    from mdm.services import build_customers
    from tenants.models import Tenant

    from .sync import sync_source

    summary = {"organizations": 0, "synced": 0, "failed": 0}
    for tenant in Tenant.objects.exclude(schema_name="public").filter(status=Tenant.ACTIVE):
        summary["organizations"] += 1
        with schema_context(tenant.schema_name):
            synced_any = False
            for source in due_sources():
                try:
                    sync_source(source.code, started_by="scheduler")
                    summary["synced"] += 1
                    synced_any = True
                except Exception:  # noqa: BLE001  (the failure is already in the source's sync history)
                    summary["failed"] += 1
            if synced_any:
                build_customers()
    return summary
