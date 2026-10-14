"""Fill free trial accounts of Snowflake, Databricks, ServiceNow and Salesforce with synthetic customers, for the
demo (python manage.py seed_cloud_source <kind> --bank axis|hdfc). Run on a developer's computer only.

Admin details are typed with hidden input and never stored. Private keys the command creates are saved in the
user's home folder (~/.lumina), never inside the project, so they cannot be committed by accident.
"""

import base64
import getpass
import urllib.parse
from pathlib import Path

from django.core.management.base import CommandError

from .cloud_demo_data import accounts, customers
from .connectors.adapters import ConnectorError
from .connectors.enterprise import DatabricksAdapter, SnowflakeAdapter, _base_url, _http

KEY_DIR = Path.home() / ".lumina"
SEEDS = {"snowflake": 4, "databricks": 5, "servicenow": 6, "salesforce": 7}
MARK = "Lumina synthetic demo record"


def _ask(label, default=""):
    value = input(f"{label}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _secret(label):
    value = getpass.getpass(f"{label} (hidden): ").strip()
    if not value:
        raise CommandError(f"{label} is needed.")
    return value


def _lit(value):
    """A SQL text literal for synthetic values (single quotes doubled), or NULL."""
    return "NULL" if value in (None, "") else "'" + str(value).replace("'", "''") + "'"


def _split_name(name):
    first, _, last = name.rpartition(" ")
    return (first or "", last or name)


def _new_key(path):
    """Create an RSA key pair, save the private key at `path`, return the public key for Snowflake."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    KEY_DIR.mkdir(exist_ok=True)
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    public = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(public).decode()


def _public_of(path):
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    public = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(public).decode()


# ---------- Snowflake ----------

def seed_snowflake(out, bank, rotate):
    account = _ask("Account identifier (e.g. MYORG-MYACCOUNT)")
    admin = _ask("Your Snowflake username (an ACCOUNTADMIN)").upper()
    warehouse = _ask("Warehouse", "COMPUTE_WH").upper()
    database = _ask("Database to create the demo in", "LUMINA_DEMO").upper()
    admin_key = KEY_DIR / f"snowflake_admin_{admin.lower()}.p8"
    if not admin_key.exists():
        public = _new_key(admin_key)
        out.write(f"First time: a key pair for {admin} was saved at {admin_key}.")
        out.write("In Snowsight, open a worksheet and run this once, then run this command again:")
        out.write(f"  ALTER USER {admin} SET RSA_PUBLIC_KEY='{public}';")
        return
    sql = SnowflakeAdapter({"account": account, "username": admin, "warehouse": warehouse, "database": "SNOWFLAKE"},
                           {"private_key": admin_key.read_text()})._run

    def run(statement):
        try:
            sql(statement)
        except ConnectorError as exc:
            raise CommandError(f"Snowflake refused: {exc}\n  {statement[:120]}") from exc

    rows = customers(bank, seed=SEEDS["snowflake"])
    run(f"CREATE DATABASE IF NOT EXISTS {database}")
    run(f"CREATE SCHEMA IF NOT EXISTS {database}.CORE")
    run(f"CREATE OR REPLACE TABLE {database}.CORE.CUSTOMERS (CUSTOMER_ID STRING, FULL_NAME STRING, DATE_OF_BIRTH DATE, "
        "GENDER STRING, PAN STRING, MOBILE STRING, EMAIL STRING, ADDRESS STRING, OCCUPATION STRING, "
        "INCOME_BAND STRING, RISK_NOTES STRING, UPDATED_AT TIMESTAMP_NTZ)")
    run(f"INSERT INTO {database}.CORE.CUSTOMERS VALUES " + ", ".join(
        f"({_lit(r['id'])}, {_lit(r['name'])}, {_lit(r['dob'])}, {_lit(r['gender'])}, {_lit(r['pan'])}, "
        f"{_lit(r['mobile'])}, {_lit(r['email'])}, {_lit(r['address'])}, {_lit(r['occupation'])}, "
        f"{_lit(r['income'])}, 'internal: never read by Lumina', {_lit(r['updated_at'])})" for r in rows))
    owned = accounts(bank, SEEDS["snowflake"])
    run(f"CREATE OR REPLACE TABLE {database}.CORE.ACCOUNTS (ACCOUNT_NO STRING, CUSTOMER_ID STRING, PRODUCT_CODE STRING, "
        "PRODUCT_NAME STRING, STATUS STRING, OPENED_ON DATE, BALANCE NUMBER(16,2), UPDATED_AT TIMESTAMP_NTZ)")
    run(f"INSERT INTO {database}.CORE.ACCOUNTS VALUES " + ", ".join(
        f"({_lit(a['account'])}, {_lit(a['customer'])}, {_lit(a['code'])}, {_lit(a['name'])}, {_lit(a['status'])}, "
        f"{_lit(a['opened'])}, {a['amount']}, {_lit(a['updated_at'])})" for a in owned))

    reader = f"LUMINA_READER_{bank.upper()}"
    for statement in [
        f"CREATE ROLE IF NOT EXISTS {reader}",
        f"GRANT USAGE ON WAREHOUSE {warehouse} TO ROLE {reader}",
        f"GRANT USAGE ON DATABASE {database} TO ROLE {reader}",
        f"GRANT USAGE ON SCHEMA {database}.CORE TO ROLE {reader}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA {database}.CORE TO ROLE {reader}",
        f"CREATE USER IF NOT EXISTS {reader} TYPE = SERVICE DEFAULT_ROLE = {reader} DEFAULT_WAREHOUSE = {warehouse}",
        f"GRANT ROLE {reader} TO USER {reader}",
    ]:
        run(statement)
    reader_key = KEY_DIR / f"snowflake_{reader.lower()}.p8"
    if rotate or not reader_key.exists():
        run(f"ALTER USER {reader} SET RSA_PUBLIC_KEY='{_new_key(reader_key)}'")
    out.write(f"{len(rows)} customers and {len(owned)} accounts written to {database}.CORE.")
    out.write("In Lumina: Add connector > Snowflake, then:")
    for key, value in [("Account identifier", account), ("Username", reader),
                       ("Private key (PEM)", f"open {reader_key} and paste everything in it"),
                       ("Warehouse", warehouse), ("Database", database), ("Role", reader),
                       ("Tables", "CORE.CUSTOMERS and CORE.ACCOUNTS")]:
        out.write(f"  {key:<20} {value}")


# ---------- Databricks ----------

def seed_databricks(out, bank, rotate):
    host = _ask("Workspace address (e.g. dbc-1234abcd-5678.cloud.databricks.com)")
    warehouse = _ask("SQL warehouse ID")
    catalog = _ask("Catalog", "workspace")
    token = _secret("Access token")
    run_sql = DatabricksAdapter({"host": host, "warehouse_id": warehouse}, {"token": token})._run

    def run(statement):
        try:
            run_sql(statement)
        except ConnectorError as exc:
            raise CommandError(f"Databricks refused: {exc}\n  {statement[:120]}") from exc

    rows = customers(bank, seed=SEEDS["databricks"])
    schema = f"`{catalog}`.lumina_demo"
    run(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    run(f"CREATE OR REPLACE TABLE {schema}.customers (customer_id STRING, full_name STRING, date_of_birth DATE, "
        "gender STRING, pan STRING, mobile STRING, email STRING, address STRING, occupation STRING, "
        "income_band STRING, updated_at TIMESTAMP)")
    run(f"INSERT INTO {schema}.customers VALUES " + ", ".join(
        f"({_lit(r['id'])}, {_lit(r['name'])}, DATE {_lit(r['dob'])}, {_lit(r['gender'])}, {_lit(r['pan'])}, "
        f"{_lit(r['mobile'])}, {_lit(r['email'])}, {_lit(r['address'])}, {_lit(r['occupation'])}, "
        f"{_lit(r['income'])}, TIMESTAMP {_lit(r['updated_at'].replace('T', ' '))})" for r in rows))
    owned = accounts(bank, SEEDS["databricks"])
    run(f"CREATE OR REPLACE TABLE {schema}.accounts (account_no STRING, customer_id STRING, product_code STRING, "
        "product_name STRING, status STRING, opened_on DATE, balance DECIMAL(16,2))")
    run(f"INSERT INTO {schema}.accounts VALUES " + ", ".join(
        f"({_lit(a['account'])}, {_lit(a['customer'])}, {_lit(a['code'])}, {_lit(a['name'])}, {_lit(a['status'])}, "
        f"DATE {_lit(a['opened'])}, {a['amount']})" for a in owned))
    out.write(f"{len(rows)} customers and {len(owned)} accounts written to {catalog}.lumina_demo.")
    out.write("In Lumina: Add connector > Databricks, with this workspace address and warehouse ID.")
    out.write("  Make a separate access token for Lumina (Settings > Developer > Access tokens).")
    out.write(f"  Tables: {catalog}.lumina_demo.customers and {catalog}.lumina_demo.accounts")


# ---------- ServiceNow ----------

def seed_servicenow(out, bank, rotate):
    instance = _ask("Instance (e.g. dev12345)")
    user = _ask("Admin username", "admin")
    password = _secret("Admin password")
    table = _ask("Table", "customer_contact")
    base = _base_url(instance, ".service-now.com")
    headers = {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}
    prefix = f"lumina.{bank}."
    try:
        _, old = _http("GET", f"{base}/api/now/table/{table}?" + urllib.parse.urlencode(
            {"sysparm_query": f"user_nameSTARTSWITH{prefix}", "sysparm_fields": "sys_id", "sysparm_limit": 500}),
            headers)
        for row in old.get("result", []):
            _http("DELETE", f"{base}/api/now/table/{table}/{row['sys_id']}", headers)
        rows = customers(bank, seed=SEEDS["servicenow"])
        for r in rows:
            first, last = _split_name(r["name"])
            _http("POST", f"{base}/api/now/table/{table}", headers, {
                "user_name": prefix + r["id"].lower(), "first_name": first, "last_name": last,
                "email": r["email"] or "", "mobile_phone": r["mobile"], "street": r["address"],
                "title": r["occupation"], "notes": MARK,
            })
    except ConnectorError as exc:
        hint = " Try the table sys_user." if table != "sys_user" else ""
        raise CommandError(f"ServiceNow refused: {exc}.{hint}") from exc
    out.write(f"{len(rows)} customers written to the {table} table (user names start with {prefix}).")
    out.write("In Lumina: Add connector > ServiceNow, then:")
    for key, value in [("Instance", instance), ("Username", "an integration user that may read the table"),
                       ("Table", table), ("Record ID column", "user_name"),
                       ("Map", "name > Full name, mobile_phone > Mobile, email > Email, street > Address")]:
        out.write(f"  {key:<20} {value}")


# ---------- Salesforce ----------

def seed_salesforce(out, bank, rotate):
    domain = _ask("My Domain address (e.g. yourbank.my.salesforce.com)")
    client_id = _ask("Connected app consumer key")
    client_secret = _secret("Connected app consumer secret")
    base = _base_url(domain, ".my.salesforce.com")
    version = "/services/data/v62.0"
    try:
        _, token = _http("POST", f"{base}/services/oauth2/token", body={
            "grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}, form=True)
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        soql = f"SELECT Id FROM Contact WHERE Description = '{MARK} ({bank})' LIMIT 200"
        _, old = _http("GET", f"{base}{version}/query?" + urllib.parse.urlencode({"q": soql}), headers)
        ids = [r["Id"] for r in old.get("records", [])]
        if ids:
            _http("DELETE", f"{base}{version}/composite/sobjects?ids={','.join(ids)}&allOrNone=false", headers)
        rows = customers(bank, seed=SEEDS["salesforce"])
        records = []
        for r in rows:
            first, last = _split_name(r["name"])
            records.append({"attributes": {"type": "Contact"}, "FirstName": first, "LastName": last,
                            "Birthdate": r["dob"], "Email": r["email"], "MobilePhone": r["mobile"],
                            "MailingStreet": r["address"], "Title": r["occupation"],
                            "Description": f"{MARK} ({bank})"})
        _http("POST", f"{base}{version}/composite/sobjects", headers, {"allOrNone": True, "records": records})
    except (ConnectorError, KeyError) as exc:
        raise CommandError(f"Salesforce refused: {exc}") from exc
    out.write(f"{len(rows)} Contacts written.")
    out.write("In Lumina: Add connector > Salesforce, with the same My Domain address and connected app, then:")
    for key, value in [("Object", "Contact"), ("Record ID column", "Id"),
                       ("Map", "Name > Full name, Birthdate > Date of birth, MobilePhone > Mobile, Email > Email, "
                               "MailingStreet > Address, Title > Occupation"),
                       ("Last updated", "LastModifiedDate")]:
        out.write(f"  {key:<20} {value}")


SEEDERS = {"snowflake": seed_snowflake, "databricks": seed_databricks, "servicenow": seed_servicenow,
           "salesforce": seed_salesforce}
