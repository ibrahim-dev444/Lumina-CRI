from django.core.management.base import BaseCommand

from compliance.services import feed_file, import_feed


class Command(BaseCommand):
    help = "Load KYC, AML and consent from this organization's compliance feed, fake_sources/<org>/compliance/kyc_aml.csv."

    def handle(self, *args, **options):
        kyc_rows, consent_changes = import_feed()
        self.stdout.write(self.style.SUCCESS(
            f"{kyc_rows} KYC records loaded from {feed_file().name}, {consent_changes} consent changes recorded."
        ))
