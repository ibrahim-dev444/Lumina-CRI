"""One organization must never see another's data. These tests guard the most important promise of Lumina."""

import pytest
from django.contrib.auth.models import Group, User
from django.db import connection
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from mdm.models import Customer
from sources.demo_data import demo_data_dir
from tenants.models import Tenant


def make_user(name, group="Data steward", password="Strong-pass-123"):
    user = User.objects.create_user(name, password=password)
    user.groups.add(Group.objects.get(name=group))
    return user


def test_each_organization_has_its_own_tables(db):
    Customer.objects.create()  # in axis
    assert Customer.objects.count() == 1
    with schema_context("hdfc"):
        assert Customer.objects.count() == 0
    assert connection.schema_name == "axis"


def test_users_belong_to_one_organization(db):
    make_user("steward.axis")
    with schema_context("hdfc"):
        assert not User.objects.filter(username="steward.axis").exists()


def test_signed_in_at_one_bank_is_not_signed_in_at_another(db):
    make_user("steward.axis")
    client = APIClient()
    signed_in = client.post("/t/axis/api/auth/login/", {"username": "steward.axis", "password": "Strong-pass-123"})
    assert signed_in.status_code == 200
    assert client.get("/t/axis/api/customers/").status_code == 200
    # Same browser, other bank: the session belongs to Axis, so HDFC treats the request as anonymous.
    assert client.get("/t/hdfc/api/customers/").status_code == 403


def test_same_username_in_two_banks_are_different_people(db):
    make_user("rm.demo", password="Axis-pass-12345")
    with schema_context("hdfc"):
        make_user("rm.demo", password="Hdfc-pass-12345")
    client = APIClient()
    wrong_bank = client.post("/t/hdfc/api/auth/login/", {"username": "rm.demo", "password": "Axis-pass-12345"})
    assert wrong_bank.status_code == 400


def test_unknown_organization_in_address_is_not_found(db):
    assert APIClient().get("/t/nobank/api/auth/me/").status_code == 404


def test_organization_lookup_answers_one_code_only(db):
    client = APIClient()
    found = client.get("/api/organizations/axis/")
    assert found.status_code == 200
    assert found.json() == {"code": "axis", "name": "Axis Bank", "brand_color": "", "logo": ""}
    assert client.get("/api/organizations/AXIS/").status_code == 200  # people may type capitals
    assert client.get("/api/organizations/nobank/").status_code == 404
    assert client.get("/api/organizations/public/").status_code == 404  # the platform is not an organization


def test_suspended_organization_cannot_be_opened(db):
    with schema_context("public"):  # organizations are managed from the shared space
        hdfc = Tenant.objects.get(schema_name="hdfc")
        hdfc.status = Tenant.SUSPENDED
        hdfc.save()
    assert APIClient().get("/api/organizations/hdfc/").status_code == 403


def test_logo_must_be_an_image_address(db):
    with schema_context("public"):
        axis = Tenant.objects.get(schema_name="axis")
        axis.logo = "<svg onload=alert(1)>"
        axis.save()
    assert APIClient().get("/api/organizations/axis/").json()["logo"] == ""
    with schema_context("public"):
        axis.logo = "data:image/png;base64,iVBORw0KGgo="
        axis.save()
    assert APIClient().get("/api/organizations/axis/").json()["logo"].startswith("data:image/png")


def test_demo_data_folder_follows_the_organization(db):
    assert demo_data_dir().name == "axis"
    with schema_context("hdfc"):
        assert demo_data_dir().name == "hdfc"
    with schema_context("public"):
        with pytest.raises(RuntimeError):
            demo_data_dir()
