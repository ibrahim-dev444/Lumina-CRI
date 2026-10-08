from django.core.management.base import BaseCommand

from mdm.services import build_customers


class Command(BaseCommand):
    help = "Match all source records into customers, then rebuild golden records and trust scores."

    def handle(self, *args, **options):
        r = build_customers()
        self.stdout.write(
            self.style.SUCCESS(
                f"{r.records} source records -> {r.customers} customers "
                f"({r.created} new, {r.merged} merged), {r.new_suggestions} new match suggestions to review"
            )
        )
