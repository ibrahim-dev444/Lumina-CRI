import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from mdm.models import Customer


@pytest.fixture
def loaded(db):
    # A customer already exists, so bootstrap_demo skips the fake data load.
    Customer.objects.create()


def test_creates_demo_and_admin_logins_from_env(loaded, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "Lumina-demo-2026!")
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "admin")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Another-strong-pass-9")
    call_command("bootstrap_demo")
    call_command("bootstrap_demo")  # safe to run on every start
    agent = User.objects.get(username="agent.demo")
    assert agent.check_password("Lumina-demo-2026!")
    assert list(agent.groups.values_list("name", flat=True)) == ["Contact centre agent"]
    assert User.objects.get(username="admin").is_superuser
    assert Customer.objects.count() == 1


def test_refuses_weak_demo_password(loaded, monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "demo")
    with pytest.raises(CommandError, match="too weak"):
        call_command("bootstrap_demo")
    assert not User.objects.filter(username="agent.demo").exists()


def test_no_logins_without_env(loaded, monkeypatch):
    for name in ["DEMO_PASSWORD", "DJANGO_SUPERUSER_USERNAME", "DJANGO_SUPERUSER_PASSWORD"]:
        monkeypatch.delenv(name, raising=False)
    call_command("bootstrap_demo")
    assert not User.objects.exists()
