import os

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from accounts.management.commands.seed_demo_users import DEMO_USERS
from mdm.models import Customer


class Command(BaseCommand):
    help = (
        "Hosted demo start-up. Loads the fake bank data once (only when there are no customers yet) and "
        "creates logins from environment variables: DEMO_PASSWORD for the four role logins, "
        "DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD for the admin. Safe to run on every start."
    )

    def handle(self, *args, **options):
        if Customer.objects.exists():
            self.stdout.write("Customers already loaded, skipping fake data.")
        else:
            call_command("load_fake_flexcube")
            for source in ["flexcube", "salesforce", "branch_csv"]:
                call_command("sync", source)
            call_command("build_customers")
            call_command("sync_compliance")

        demo_password = os.getenv("DEMO_PASSWORD", "")
        if demo_password:
            self._check(demo_password, "DEMO_PASSWORD")
            for username, first, last, group_name in DEMO_USERS:
                user, _ = User.objects.get_or_create(
                    username=username, defaults={"first_name": first, "last_name": last}
                )
                user.set_password(demo_password)
                user.save()
                user.groups.set([Group.objects.get(name=group_name)])
            self.stdout.write(f"Demo logins ready: {', '.join(u[0] for u in DEMO_USERS)}")

        admin_name = os.getenv("DJANGO_SUPERUSER_USERNAME", "")
        admin_password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        if admin_name and admin_password:
            self._check(admin_password, "DJANGO_SUPERUSER_PASSWORD")
            admin, _ = User.objects.get_or_create(username=admin_name)
            admin.is_staff = admin.is_superuser = True
            admin.set_password(admin_password)
            admin.save()
            self.stdout.write(f"Admin login ready: {admin_name}")

    def _check(self, password, name):
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(f"{name} is too weak: {' '.join(exc.messages)}") from exc
