import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django_tenants.utils import schema_context


@pytest.fixture
def no_data_load(monkeypatch):
    # The test organizations already exist; skip loading synthetic data (it needs the fake core banking DB).
    monkeypatch.setattr("tenants.management.commands.setup_tenants.load_demo_data", lambda code, stdout: None)


def test_sets_logins_in_every_organization_and_the_platform(db, no_data_load, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "Lumina-demo-2026!")
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Another-strong-pass-9")
    call_command("bootstrap_demo")
    call_command("bootstrap_demo")  # safe to run on every start
    for org in ["axis", "hdfc"]:
        with schema_context(org):
            agent = User.objects.get(username="agent.demo")
            assert agent.check_password("Lumina-demo-2026!")
            assert list(agent.groups.values_list("name", flat=True)) == ["Contact centre agent"]
            assert User.objects.get(username="admin").is_superuser
    with schema_context("public"):
        assert User.objects.get(username="admin").is_superuser
        assert not User.objects.filter(username="agent.demo").exists()  # role logins live inside banks only


def test_refuses_weak_demo_password(db, no_data_load, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "demo")
    with pytest.raises(CommandError, match="too weak"):
        call_command("bootstrap_demo")
    assert not User.objects.filter(username="agent.demo").exists()


def test_no_logins_without_env(db, no_data_load, monkeypatch):
    for name in ["DEMO_PASSWORD", "DJANGO_SUPERUSER_USERNAME", "DJANGO_SUPERUSER_PASSWORD"]:
        monkeypatch.delenv(name, raising=False)
    call_command("bootstrap_demo")
    assert not User.objects.exists()
