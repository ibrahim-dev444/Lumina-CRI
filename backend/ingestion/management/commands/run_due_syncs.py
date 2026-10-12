from django.core.management.base import BaseCommand

from ingestion.schedule import run_due_syncs


class Command(BaseCommand):
    help = "Sync every source that is due by its schedule, in every active organization (run hourly)."

    def handle(self, *args, **options):
        summary = run_due_syncs()
        self.stdout.write(
            f"{summary['organizations']} organizations checked, {summary['synced']} sources synced, "
            f"{summary['failed']} failed."
        )
