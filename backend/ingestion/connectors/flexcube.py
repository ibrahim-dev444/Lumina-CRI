import psycopg
from django.conf import settings
from psycopg.rows import dict_row

from .base import BaseConnector


class FlexcubeConnector(BaseConnector):
    """Reads customers from FLEXCUBE's CUST_MASTER table.

    In development this is the fake src_flexcube database. In the bank it will be a
    read-only copy of the real Oracle database; only the connection changes.
    """

    source_code = "flexcube"
    sensitive_columns = {"PAN_NO": "pan", "AADHAAR_NO": "aadhaar", "CKYC_NO": "ckyc"}

    def fetch(self):
        if not settings.FLEXCUBE_DB_URL:
            raise RuntimeError("FLEXCUBE_DB_URL is not set. Add it to your .env file.")
        with psycopg.connect(settings.FLEXCUBE_DB_URL, row_factory=dict_row) as conn:
            return conn.execute('SELECT * FROM "CUST_MASTER" ORDER BY "CUST_ID"').fetchall()

    def record_id(self, raw):
        return raw["CUST_ID"]

    def to_standard(self, raw):
        return {
            "name": raw["CUST_NAME"],
            "father_name": raw.get("FATHER_NAME"),
            "dob": raw["DOB"],
            "gender": raw.get("GENDER"),
            "pan": raw.get("PAN_NO"),
            "aadhaar": raw.get("AADHAAR_NO"),
            "ckyc": raw.get("CKYC_NO"),
            "mobile": raw["MOB_NO"],
            "email": raw["EMAIL_ID"],
            "address": raw["ADDR1"],
            "perm_address": raw.get("PERM_ADDR"),
            "occupation": raw.get("OCCUPATION"),
            "income": raw.get("ANNUAL_INCOME"),
            "source_updated_at": raw["LAST_UPD_DT"],
        }
