"""Fill a cloud database with synthetic customers and create a read-only login for Lumina (Phase 6).

    python manage.py seed_cloud_source postgres --bank axis
    python manage.py seed_cloud_source mysql --bank hdfc      (asks host, port, user, password one by one)
    python manage.py seed_cloud_source mongodb --bank axis

The command asks for the database's admin connection string with hidden typing, so it never appears in the
screen, the shell history or a chat. It prints the read-only login once: type those details into Lumina's
connector screen. Run it again any time to reset the rows: the read-only login keeps its password, so the
connector in Lumina keeps working. Add --new-password to change it (then type the new one into Lumina).
"""

import getpass
import secrets
from urllib.parse import quote, unquote, urlparse

from django.core.management.base import BaseCommand, CommandError

from ingestion.cloud_demo_data import customers

SEEDS = {"postgres": 1, "mysql": 2, "mongodb": 3}


class Command(BaseCommand):
    help = "Fill a cloud database with synthetic customers and create a read-only login for Lumina."

    def add_arguments(self, parser):
        parser.add_argument("kind", choices=["postgres", "mysql", "mongodb"])
        parser.add_argument("--bank", choices=["axis", "hdfc"], required=True)
        parser.add_argument("--count", type=int, default=24)
        parser.add_argument("--new-password", action="store_true", help="Give the read-only login a new password.")

    def handle(self, *args, kind, bank, count, new_password=False, **options):
        if kind == "mysql":
            url = self._ask_mysql()
        else:
            url = getpass.getpass(f"Paste the {kind} ADMIN connection string (hidden), then press Enter: ").strip()
        if not url:
            raise CommandError("No connection string given.")
        rows = customers(bank, count=count, seed=SEEDS[kind])
        self.rotate = new_password
        reader_password = secrets.token_urlsafe(18)
        getattr(self, f"_{kind}")(url, rows, bank, reader_password)

    # ---------- PostgreSQL (e.g. a second Neon project) ----------

    def _postgres(self, url, rows, bank, password):
        import psycopg

        role = f"lumina_reader_{bank}"
        parts = urlparse(url)
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("CREATE SCHEMA IF NOT EXISTS core")
            conn.execute("DROP TABLE IF EXISTS core.customers")
            conn.execute(
                "CREATE TABLE core.customers (cust_id varchar(20) PRIMARY KEY, cust_name varchar(100) NOT NULL, "
                "date_of_birth date, gender_code char(1), pan_no varchar(10), mobile_no varchar(20), "
                "email_id varchar(120), address_line varchar(200), occupation varchar(60), annual_income varchar(40), "
                "internal_risk_note text, last_updated timestamp)"
            )
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO core.customers VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        (r["id"], r["name"].upper() if i % 3 == 0 else r["name"], r["dob"], r["gender"], r["pan"],
                         r["mobile"], r["email"], r["address"], r["occupation"], r["income"],
                         "internal note: never read by Lumina", r["updated_at"])
                        for i, r in enumerate(rows)
                    ],
                )
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role]).fetchone()
            from psycopg import sql

            if not exists:
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
            elif self.rotate:
                conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
            else:
                password = None
            database = parts.path.lstrip("/")
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(role)))
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA core TO {}").format(sql.Identifier(role)))
            conn.execute(sql.SQL("GRANT SELECT ON core.customers TO {}").format(sql.Identifier(role)))
        self._report(len(rows), "PostgreSQL", [
            ("Server address", parts.hostname), ("Port", str(parts.port or 5432)), ("Database name", database),
            ("Username", role), ("Password", password), ("Encryption (SSL)", "Required"),
            ("Table to choose in Discover", "core.customers"),
        ])

    # ---------- MySQL (e.g. TiDB Cloud Serverless) ----------

    def _ask_mysql(self):
        """Ask for each part separately (as TiDB's Connect screen shows them), so nothing needs URL-escaping."""
        host = input("Host (e.g. gateway01.ap-southeast-1.prod.aws.tidbcloud.com): ").strip()
        if not host or host.lower() in {"host", "<host>"} or "." not in host:
            raise CommandError("Type the real host name from the database's Connect screen.")
        port = input("Port [4000]: ").strip() or "4000"
        user = input("User (e.g. 3Abc123.root): ").strip()
        password = getpass.getpass("Password (hidden): ")
        if not user or not password:
            raise CommandError("User and password are needed.")
        return f"mysql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{int(port)}/lumina_source"

    def _mysql(self, url, rows, bank, password):
        import ssl

        import pymysql

        parts = urlparse(url)
        database = parts.path.lstrip("/") or "lumina_source"
        admin = unquote(parts.username or "")
        # TiDB Cloud Serverless user names carry a prefix ("abc123.root"); new users need the same prefix.
        prefix = admin.split(".", 1)[0] + "." if "." in admin else ""
        reader = f"{prefix}lumina_reader"
        conn = pymysql.connect(
            host=parts.hostname, port=parts.port or 3306, user=admin, password=unquote(parts.password or ""),
            ssl=ssl.create_default_context(), autocommit=True,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
                cur.execute(f"USE `{database}`")
                cur.execute("DROP TABLE IF EXISTS customer_master")
                cur.execute(
                    "CREATE TABLE customer_master (CUSTOMER_ID varchar(20) PRIMARY KEY, FULL_NAME varchar(100) NOT NULL, "
                    "DOB date, SEX varchar(6), PAN varchar(10), PHONE varchar(20), EMAIL varchar(120), "
                    "ADDRESS varchar(200), PROFESSION varchar(60), INCOME_BAND varchar(40), CREDIT_SCORE int, "
                    "MODIFIED_AT datetime)"
                )
                cur.executemany(
                    "INSERT INTO customer_master VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        (r["id"], r["name"], r["dob"], {"M": "Male", "F": "Female"}[r["gender"]], r["pan"],
                         "+91 " + r["mobile"], r["email"], r["address"], r["occupation"], r["income"], 600 + i * 7,
                         r["updated_at"].replace("T", " "))
                        for i, r in enumerate(rows)
                    ],
                )
                cur.execute("SELECT COUNT(*) FROM mysql.user WHERE User = %s", [reader])
                exists = cur.fetchone()[0] > 0
                if not exists:
                    cur.execute("CREATE USER %s@'%%' IDENTIFIED BY %s", [reader, password])
                elif self.rotate:
                    cur.execute("ALTER USER %s@'%%' IDENTIFIED BY %s", [reader, password])
                else:
                    password = None
                cur.execute(f"GRANT SELECT ON `{database}`.`customer_master` TO %s@'%%'", [reader])
        finally:
            conn.close()
        self._report(len(rows), "MySQL", [
            ("Server address", parts.hostname), ("Port", str(parts.port or 3306)), ("Database name", database),
            ("Username", reader), ("Password", password), ("Encryption (TLS)", "On"),
            ("Table to choose in Discover", "customer_master"),
        ])

    # ---------- MongoDB (e.g. MongoDB Atlas) ----------

    def _mongodb(self, url, rows, bank, password):
        import pymongo

        client = pymongo.MongoClient(url, serverSelectionTimeoutMS=10000)
        database = "lumina_source"
        try:
            collection = client[database]["app_users"]
            collection.drop()
            collection.insert_many([
                {
                    "userId": r["id"],
                    "profile": {"fullName": r["name"], "dob": r["dob"], "gender": r["gender"]},
                    "contact": {"mobile": r["mobile"], "email": r["email"]},
                    "kyc": {"pan": r["pan"]},
                    "address": r["address"],
                    "deviceTokens": ["never-read-by-lumina"],
                    "updatedAt": r["updated_at"],
                }
                for r in rows
            ])
        finally:
            client.close()
        self.stdout.write(self.style.SUCCESS(f"{len(rows)} synthetic customers written to {database}.app_users."))
        self.stdout.write(
            "MongoDB Atlas creates logins in its own screens, not from here. In Atlas: Database Access > Add New "
            f"Database User > Password; built-in role 'Only read any database' (or read on {database}). Then copy the "
            "connection string with that user into Lumina, database name lumina_source, collection app_users."
        )

    def _report(self, count, label, details):
        self.stdout.write(self.style.SUCCESS(f"{count} synthetic customers written to {label}."))
        if dict(details)["Password"] is None:
            self.stdout.write("Read-only login unchanged: the connector in Lumina keeps working. Press Sync now there.")
            return
        self.stdout.write("Read-only login for Lumina (shown once; type these into the connector screen):")
        for key, value in details:
            self.stdout.write(f"  {key:<28} {value}")
