import json
from datetime import datetime
from pathlib import Path

from django.conf import settings

from .base import BaseConnector


class SalesforceConnector(BaseConnector):
    """Reads Contacts in the shape the Salesforce REST API returns them.

    In development we read a saved API response from a JSON file. The real connector will
    call GET /services/data/v60.0/query?q=SELECT ... FROM Contact and get the same shape,
    so only fetch() changes.
    """

    source_code = "salesforce"

    def fetch(self):
        path = Path(settings.SALESFORCE_MOCK_FILE)
        if not path.exists():
            raise RuntimeError(f"Salesforce mock file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))["records"]

    def record_id(self, raw):
        return raw["Id"]

    def to_standard(self, raw):
        name = " ".join(part for part in [raw.get("FirstName"), raw.get("LastName")] if part)
        address = ", ".join(
            part for part in [raw.get("MailingStreet"), raw.get("MailingCity"), raw.get("MailingPostalCode")] if part
        )
        modified = raw.get("LastModifiedDate")
        return {
            "name": name,
            "mobile": raw.get("MobilePhone"),
            "email": raw.get("Email"),
            "address": address,
            "dob": raw.get("Birthdate"),
            # Salesforce sends times like 2026-02-14T11:32:08.000+0000 (always UTC).
            "source_updated_at": datetime.strptime(modified, "%Y-%m-%dT%H:%M:%S.%f%z") if modified else None,
        }
