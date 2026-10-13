from django.core.management.base import BaseCommand

from ingestion.retire import plan, remove_demo_sources


class Command(BaseCommand):
    help = (
        "Remove the built-in demo sources (fake FLEXCUBE, Salesforce export, branch files), their records and the "
        "customers only they described, in the current organization (use tenant_command ... --schema=<code>). "
        "Cannot be undone. Use --dry-run first to see what would go."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only show what would be removed.")

    def handle(self, *args, dry_run=False, **options):
        result = plan() if dry_run else remove_demo_sources()
        verb = "Would remove" if dry_run else "Removed"
        self.stdout.write(
            f"{verb} {result.sources} demo sources, {result.records} records, {result.customers_removed} customers "
            f"and {result.corrections_removed} corrections."
        )
