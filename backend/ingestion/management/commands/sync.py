from django.core.management.base import BaseCommand, CommandError

from ingestion.sync import sync_source


class Command(BaseCommand):
    help = "Pull customers from one source system. Example: python manage.py sync flexcube"

    def add_arguments(self, parser):
        parser.add_argument("source_code", help="Source.code to sync, e.g. flexcube")

    def handle(self, *args, source_code, **options):
        try:
            result = sync_source(source_code)
        except Exception as exc:
            raise CommandError(f"Sync of '{source_code}' failed: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"{source_code}: {result.fetched} fetched, {result.created} new, {result.updated} updated"
            )
        )
