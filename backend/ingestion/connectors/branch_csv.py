import csv
from datetime import datetime, time
from pathlib import Path

from django.conf import settings

from ..clean import clean_date
from .base import BaseConnector


class BranchCsvConnector(BaseConnector):
    """Reads the spreadsheets branches upload, one or more .csv files in BRANCH_CSV_DIR.

    Expected columns: Ref No, Cust Name, Mobile No, Email, Address, DOB, Updated On.
    Dates are written the Indian way, DD/MM/YYYY.
    """

    source_code = "branch_csv"
    sensitive_columns = {"PAN": "pan", "Aadhaar": "aadhaar"}

    def fetch(self):
        folder = Path(settings.BRANCH_CSV_DIR)
        if not folder.is_dir():
            raise RuntimeError(f"Branch CSV folder not found: {folder}")
        rows = []
        for path in sorted(folder.glob("*.csv")):
            # utf-8-sig also handles the invisible marker Excel puts at the start of saved CSV files.
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    rows.append({**row, "_file": path.name})
        return rows

    def record_id(self, raw):
        return raw["Ref No"].strip()

    def to_standard(self, raw):
        updated = clean_date(raw.get("Updated On"))
        return {
            "name": raw.get("Cust Name"),
            "mobile": raw.get("Mobile No"),
            "email": raw.get("Email"),
            "address": raw.get("Address"),
            "dob": raw.get("DOB"),
            "father_name": raw.get("Father Name"),
            "gender": raw.get("Gender"),
            "pan": raw.get("PAN"),
            "aadhaar": raw.get("Aadhaar"),
            "perm_address": raw.get("Permanent Address"),
            "occupation": raw.get("Occupation"),
            "income": raw.get("Annual Income"),
            # The sheet has only a date, so we take the start of that day.
            "source_updated_at": datetime.combine(updated, time.min) if updated else None,
        }
