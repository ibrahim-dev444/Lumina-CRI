from datetime import date, datetime, timezone

from ingestion.clean import clean_record
from ingestion.connectors.branch_csv import BranchCsvConnector
from ingestion.connectors.salesforce import SalesforceConnector

SALESFORCE_ROW = {
    "Id": "003Dn00000A1001AAA",
    "FirstName": "Sooresh",
    "LastName": "Kumar",
    "MobilePhone": "98221 07788",
    "Email": "skumar84@webmail.example",
    "MailingStreet": "Plot 7, Sector 21",
    "MailingCity": "Nigdi, Pune",
    "MailingPostalCode": "411044",
    "Birthdate": "1984-07-12",
    "LastModifiedDate": "2026-02-14T11:32:08.000+0000",
}

CSV_ROW = {
    "Ref No": " BR-PUN-0001 ",
    "Cust Name": "Suresh K",
    "Mobile No": "9822107788",
    "Email": "suresh.kumar@mail.example",
    "Address": "Kothrud, Pune",
    "DOB": "12/07/1984",
    "Updated On": "05/09/2026",
}


def test_salesforce_maps_contact_to_standard_fields():
    connector = SalesforceConnector()
    assert connector.record_id(SALESFORCE_ROW) == "003Dn00000A1001AAA"
    std = clean_record(connector.to_standard(SALESFORCE_ROW))
    assert {k: std[k] for k in ["name", "mobile", "email", "address", "dob", "source_updated_at"]} == {
        "name": "Sooresh Kumar",
        "mobile": "9822107788",
        "email": "skumar84@webmail.example",
        "address": "Plot 7, Sector 21, Nigdi, Pune, 411044",
        "dob": date(1984, 7, 12),
        "source_updated_at": datetime(2026, 2, 14, 11, 32, 8, tzinfo=timezone.utc),
    }


def test_salesforce_missing_birthdate_and_last_name():
    row = {**SALESFORCE_ROW, "LastName": None, "Birthdate": None}
    std = clean_record(SalesforceConnector().to_standard(row))
    assert std["name"] == "Sooresh"
    assert std["dob"] is None


def test_branch_csv_maps_columns_and_reads_day_first_dates():
    connector = BranchCsvConnector()
    assert connector.record_id(CSV_ROW) == "BR-PUN-0001"
    std = clean_record(connector.to_standard(CSV_ROW))
    assert std["dob"] == date(1984, 7, 12)
    assert std["source_updated_at"] == datetime(2026, 9, 5, 0, 0)


def test_fake_files_load():
    assert len(SalesforceConnector().fetch()) == 8
    assert len(BranchCsvConnector().fetch()) == 6
