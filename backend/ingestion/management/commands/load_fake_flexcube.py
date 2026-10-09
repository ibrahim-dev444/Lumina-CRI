from pathlib import Path

import psycopg
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# The same SQL Docker runs on first start, so there is one copy of the fake data.
SQL_FILE = Path(settings.BASE_DIR).parent / "docker" / "postgres" / "init" / "01-flexcube.sql"


class Command(BaseCommand):
    help = "Re-create the fake FLEXCUBE table (src_flexcube.CUST_MASTER) from docker/postgres/init/01-flexcube.sql."

    def handle(self, *args, **options):
        if not settings.FLEXCUBE_DB_URL:
            raise CommandError("FLEXCUBE_DB_URL is not set in .env.")
        text = SQL_FILE.read_text(encoding="utf-8")
        # Skip the database creation part; run only what comes after "\connect src_flexcube".
        marker = "\\connect src_flexcube"
        if marker not in text:
            raise CommandError(f"Could not find '{marker}' in {SQL_FILE}.")
        sql = text.split(marker, 1)[1]
        with psycopg.connect(settings.FLEXCUBE_DB_URL, autocommit=True) as conn:
            conn.execute(sql)
            rows = conn.execute('SELECT count(*) FROM "CUST_MASTER"').fetchone()[0]
        self.stdout.write(self.style.SUCCESS(f"Fake FLEXCUBE reloaded: {rows} customers."))
