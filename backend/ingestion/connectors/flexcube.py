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
            "mobile": raw["MOB_NO"],
            "email": raw["EMAIL_ID"],
            "address": raw["ADDR1"],
            "dob": raw["DOB"],
            "source_updated_at": raw["LAST_UPD_DT"],
        }
