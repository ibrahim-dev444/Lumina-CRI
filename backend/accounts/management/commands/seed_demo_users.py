import secrets

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

DEMO_USERS = [
    ("rm.demo", "Relationship", "Manager", "Relationship manager"),
    ("agent.demo", "Contact", "Agent", "Contact centre agent"),
    ("steward.demo", "Data", "Steward", "Data steward"),
    ("compliance.demo", "Compliance", "Officer", "Compliance officer"),
]


class Command(BaseCommand):
    help = "Create one demo login per role, with fresh random passwords printed once. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Refusing to create demo users when DJANGO_DEBUG is not true.")
        for username, first, last, group_name in DEMO_USERS:
            password = secrets.token_urlsafe(9)
            user, _ = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last})
            user.set_password(password)
            user.save()
            user.groups.set([Group.objects.get(name=group_name)])
            self.stdout.write(f"{group_name:<22} {username:<17} {password}")
        self.stdout.write(self.style.WARNING("Passwords are shown only now. Run again to reset them."))
