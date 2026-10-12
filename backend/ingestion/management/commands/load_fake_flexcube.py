import psycopg
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from psycopg import sql

from sources.demo_data import demo_data_dir


class Command(BaseCommand):
    help = (
        "Re-create this organization's fake FLEXCUBE table (<org>.CUST_MASTER in src_flexcube) from "
        "fake_sources/<org>/flexcube.sql. Run per organization: tenant_command load_fake_flexcube --schema=axis"
    )

    def handle(self, *args, **options):
        if not settings.FLEXCUBE_DB_URL:
            raise CommandError("FLEXCUBE_DB_URL is not set in .env.")
        sql_file = demo_data_dir() / "flexcube.sql"
        if not sql_file.exists():
            raise CommandError(f"No core banking data for this organization: {sql_file}")
        schema = sql.Identifier(connection.schema_name)
        with psycopg.connect(settings.FLEXCUBE_DB_URL, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema))
            conn.execute(sql.SQL("SET search_path TO {}").format(schema))
            conn.execute(sql_file.read_text(encoding="utf-8"))
            rows = conn.execute('SELECT count(*) FROM "CUST_MASTER"').fetchone()[0]
        self.stdout.write(self.style.SUCCESS(f"Fake FLEXCUBE for {connection.schema_name} reloaded: {rows} customers."))
