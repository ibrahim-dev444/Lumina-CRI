from datetime import date, datetime

from ingestion.clean import clean_record
from ingestion.connectors.flexcube import FlexcubeConnector

ROW = {
    "CUST_ID": "FX0000101",
    "CUST_NAME": "SURESH KUMAR",
    "MOB_NO": "+91 98221 04521",
    "EMAIL_ID": "suresh.kumar@mail.example",
    "ADDR1": "14 Shanti Apts., Kothrud, Pune 411038",
    "DOB": date(1984, 7, 12),
    "PAN_NO": "ABCPK1234F",
    "LAST_UPD_DT": datetime(2025, 11, 2, 10, 15),
}


def test_maps_flexcube_columns_to_standard_fields():
    connector = FlexcubeConnector()
    assert connector.record_id(ROW) == "FX0000101"
    std = clean_record(connector.to_standard(ROW))
    assert std | {} == std  # a plain dict
    assert {k: std[k] for k in ["name", "mobile", "email", "address", "dob", "pan", "source_updated_at"]} == {
        "name": "Suresh Kumar",
        "mobile": "9822104521",
        "email": "suresh.kumar@mail.example",
        "address": "14 Shanti Apts., Kothrud, Pune 411038",
        "dob": date(1984, 7, 12),
        "pan": "ABCPK1234F",  # still plain here; sync encrypts it before saving
        "source_updated_at": datetime(2025, 11, 2, 10, 15),
    }
