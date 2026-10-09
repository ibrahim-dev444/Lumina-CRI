from django.core.management.base import BaseCommand

from compliance.services import FEED_FILE, import_feed


class Command(BaseCommand):
    help = "Load KYC, AML and consent from the (fake) compliance feed, fake_sources/compliance/kyc_aml.csv."

    def handle(self, *args, **options):
        kyc_rows, consent_changes = import_feed()
        self.stdout.write(self.style.SUCCESS(
            f"{kyc_rows} KYC records loaded from {FEED_FILE.name}, {consent_changes} consent changes recorded."
        ))
