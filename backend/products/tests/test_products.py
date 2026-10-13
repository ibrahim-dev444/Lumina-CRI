"""Accounts, deposits, loans and cards: read from a connector's second table, attached to the right customer,
amounts only for roles that may see them, account numbers never stored in full."""

import uuid
from decimal import Decimal

import psycopg
import pytest
from django.conf import settings as django_settings
from django.contrib.auth.models import Group, User
from django.db import connection
from rest_framework.test import APIClient

from mdm.models import Customer
from products.models import Holding
from products.services import classify_status, classify_type, clean_amount


@pytest.mark.parametrize("texts, expected", [
    (("SB",), "savings"), (("CA",), "current"), (("FD",), "deposit"), (("HL",), "home_loan"),
    (("CC",), "credit_card"), (("", "Platinum Credit Card"), "credit_card"), (("VL",), "vehicle_loan"),
    (("Car Loan",), "vehicle_loan"), (("LAP",), "loan"), (("XYZ", "Gold Loan"), "loan"), (("XYZ",), "other"),
])
def test_product_types_from_bank_codes_and_names(texts, expected):
    assert classify_type(*texts) == expected


@pytest.mark.parametrize("text, expected", [
    ("ACTIVE", "active"), ("Regular", "active"), ("", "active"), ("NPA", "overdue"), ("Overdue", "overdue"),
    ("DORMANT", "dormant"), ("Inoperative", "dormant"), ("CLOSED", "closed"), ("Settled", "closed"),
])
def test_statuses(text, expected):
    assert classify_status(text) == expected


def test_amounts():
    assert clean_amount("Rs 12,45,000.50") == Decimal("1245000.50")
    assert clean_amount(64000) == Decimal("64000.00") and clean_amount("n/a") is None and clean_amount("") is None


@pytest.fixture
def core_system(db, settings):
    """A real core banking schema (customers + accounts) on the test database server, on its own connection."""
    settings.CONNECTORS_ALLOW_PRIVATE_HOSTS = True
    db_settings = django_settings.DATABASES["default"]
    schema = f"core_{uuid.uuid4().hex[:8]}"
    params = dict(host=db_settings["HOST"], port=db_settings["PORT"], dbname=connection.settings_dict["NAME"],
                  user=db_settings["USER"], password=db_settings["PASSWORD"], autocommit=True)
    with psycopg.connect(**params) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
        conn.execute(f'CREATE TABLE "{schema}".customers (cust_id text, cust_name text, mobile text)')
        conn.execute(f"INSERT INTO \"{schema}\".customers VALUES ('C1', 'Asha Rao', '9000000001'), "
                     "('C2', 'Vikram Shetty', '9000000002')")
        conn.execute(f'CREATE TABLE "{schema}".accounts (acct_no text, cust_id text, product_code text, '
                     'product_desc text, acct_status text, open_date date, curr_balance numeric, branch text)')
        conn.execute(f"INSERT INTO \"{schema}\".accounts VALUES "
                     "('912010045671234', 'C1', 'SB', 'Prime Savings', 'ACTIVE', '2019-04-01', 185000.50, 'BR1'), "
                     "('912010045675678', 'C1', 'CC', 'Platinum Card', 'OVERDUE', '2021-06-15', 64000, 'BR1'), "
                     "('912010045679999', 'C2', 'HL', 'Home Loan', 'ACTIVE', '2018-01-20', 3850000, 'BR2')")

    def run(sql):
        with psycopg.connect(**params) as conn:
            conn.execute(sql.replace("{schema}", f'"{schema}"'))

    yield schema, db_settings, run
    run("DROP SCHEMA {schema} CASCADE")


def _admin():
    c = APIClient()
    c.force_authenticate(User.objects.create_user("prod.admin", password="Strong-pass-123", is_superuser=True))
    return c


def _as(group):
    user = User.objects.create_user(f"u.{uuid.uuid4().hex[:6]}", password="Strong-pass-123")
    user.groups.add(Group.objects.get(name=group))
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def connected(core_system):
    schema, db, run = core_system
    admin = _admin()
    code = admin.post("/api/connectors/", {
        "name": "Core banking", "connector_type": "postgresql", "trust": 85,
        "settings": {"host": db["HOST"], "port": str(db["PORT"]), "database": connection.settings_dict["NAME"],
                     "username": db["USER"], "password": db["PASSWORD"], "sslmode": "prefer"},
    }, format="json").json()["code"]
    assert admin.put(f"/api/connectors/{code}/mapping/", {
        "object": f"{schema}.customers", "id_column": "cust_id", "fields": {"name": "cust_name", "mobile": "mobile"},
    }, format="json").status_code == 200
    saved = admin.put(f"/api/connectors/{code}/accounts-mapping/", {
        "object": f"{schema}.accounts", "id_column": "acct_no", "customer_column": "cust_id",
        "fields": {"product_type": "product_code", "product_name": "product_desc", "status": "acct_status",
                   "opened_on": "open_date", "balance": "curr_balance"},
    }, format="json")
    assert saved.status_code == 200, saved.json()
    synced = admin.post(f"/api/sources/{code}/sync/")
    assert synced.status_code == 200, synced.json()
    assert synced.json()["accounts"] == 3
    return admin, code, run


def _customer(name):
    return next(c for c in Customer.objects.all() if c.golden_fields.get(field="name").value == name)


def test_products_join_the_right_customer_with_amounts_for_front_line_roles(connected):
    asha = _customer("Asha Rao")
    body = _as("Relationship manager").get(f"/api/customers/{asha.id}/").json()["products"]
    assert body["count"] == 2 and body["overdue"] == 1 and not body["amounts_hidden"]
    assert body["deposits"] == "185000.50" and body["owed"] == "64000.00"
    items = {i["type"]: i for i in body["items"]}
    assert set(items) == {"savings", "credit_card"}
    assert items["savings"]["account"] == "XX1234" and items["savings"]["balance"] == "185000.50"
    assert items["credit_card"]["status"] == "overdue" and items["savings"]["opened_on"] == "2019-04-01"


def test_stewards_see_products_but_not_amounts(connected):
    body = _as("Data steward").get(f"/api/customers/{_customer('Asha Rao').id}/").json()["products"]
    assert body["amounts_hidden"] and body["deposits"] is None
    assert body["count"] == 2 and all(i["balance"] is None for i in body["items"])


def test_full_account_numbers_are_never_stored(connected):
    for h in Holding.objects.all():
        assert "91201004567" not in f"{h.account_key}{h.account_last4}{h.product_name}{h.customer_ref}"
    assert not Holding.objects.filter(account_key__contains="1234").exclude(account_last4="1234").exists()


def test_accounts_the_source_drops_are_removed_and_mapping_survives_customer_remap(connected):
    admin, code, run = connected
    run("DELETE FROM {schema}.accounts WHERE product_code = 'CC'")
    customers_mapping = admin.get("/api/sources/").json()["results"]
    source = next(s for s in customers_mapping if s["code"] == code)
    # Saving the customer mapping again keeps the accounts mapping.
    admin.put(f"/api/connectors/{code}/mapping/", {
        "object": source["mapping"]["object"], "id_column": "cust_id", "fields": {"name": "cust_name"},
    }, format="json")
    assert admin.post(f"/api/sources/{code}/sync/").json()["accounts"] == 2
    assert not Holding.objects.filter(product_type="credit_card").exists()
    # Stopping the accounts mapping removes the products it brought.
    assert admin.delete(f"/api/connectors/{code}/accounts-mapping/").status_code == 200
    assert not Holding.objects.exists()


def test_accounts_mapping_is_checked(connected):
    admin, code, _ = connected
    bad = admin.put(f"/api/connectors/{code}/accounts-mapping/", {
        "object": "x", "id_column": "acct_no", "customer_column": "", "fields": {"status": "acct_status"},
    }, format="json")
    assert bad.status_code == 400
    steward = _as("Data steward")
    assert steward.put(f"/api/connectors/{code}/accounts-mapping/", {}, format="json").status_code == 403
