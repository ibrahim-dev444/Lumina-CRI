"""Many CSV files on one file-upload connector: upload several at once, suspend, resume and remove them."""

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from ingestion.models import SourceRecord
from interactions.models import Interaction
from mdm.models import Customer

HEADER = "Ref,Full Name,Phone\n"
NORTH = HEADER + "N1,Asha Rao,9000000001\nN2,Vikram Shetty,9000000002\nS1,Old Name,9000000003\n"
SOUTH = HEADER + "S1,Sunita Menon,9000000003\nS2,Karan Gill,9000000004\n"


def csv_file(name, text):
    return SimpleUploadedFile(name, text.encode(), content_type="text/csv")


@pytest.fixture
def admin(db):
    c = APIClient()
    c.force_authenticate(User.objects.create_user("files.admin", password="Strong-pass-123", is_superuser=True))
    return c


@pytest.fixture
def branches(admin):
    """A connector with two branch files: North (older) and South (newer). S1 is in both."""
    code = admin.post("/api/connectors/", {"name": "Branch files", "connector_type": "file_upload", "trust": 40},
                      format="json").json()["code"]
    assert admin.post(f"/api/connectors/{code}/upload/", {"files": [csv_file("north.csv", NORTH)]},
                      format="multipart").status_code == 200
    assert admin.put(f"/api/connectors/{code}/mapping/", {
        "object": "Uploaded files", "id_column": "Ref", "fields": {"name": "Full Name", "mobile": "Phone"},
    }, format="json").status_code == 200
    up = admin.post(f"/api/connectors/{code}/upload/", {"files": [csv_file("south.csv", SOUTH)]}, format="multipart")
    assert up.status_code == 200, up.json()
    files = {f["name"]: f["id"] for f in admin.get(f"/api/connectors/{code}/files/").json()}
    return code, files


def visible_names():
    return sorted(Customer.objects.visible().filter(golden_fields__field="name")
                  .values_list("golden_fields__value", flat=True))


def test_every_active_file_is_read_and_the_newest_wins(admin, branches):
    assert visible_names() == ["Asha Rao", "Karan Gill", "Sunita Menon", "Vikram Shetty"]  # S1 from south.csv
    code, files = branches
    assert SourceRecord.objects.get(source__code=code, source_record_id="S1").origin_file_id == files["south.csv"]


def test_several_files_at_once_each_checked_against_the_mapping(admin, branches):
    code, _ = branches
    batch = [csv_file("east.csv", HEADER + "E1,Ravi Das,9000000005\n"),
             csv_file("west.csv", "Ref,Name\nW1,Wrong columns\n"),
             csv_file("empty.csv", HEADER)]
    answer = admin.post(f"/api/connectors/{code}/upload/", {"files": batch}, format="multipart").json()["files"]
    assert [(f["name"], f["ok"]) for f in answer] == [("east.csv", True), ("west.csv", False), ("empty.csv", False)]
    assert "Full Name" in answer[1]["error"] and "Ravi Das" in visible_names()
    too_many = [csv_file(f"f{i}.csv", HEADER + f"X{i},P {i},9000000{i:03d}\n") for i in range(21)]
    assert admin.post(f"/api/connectors/{code}/upload/", {"files": too_many},
                      format="multipart").status_code == 400


def test_suspend_hides_only_that_files_customers_and_resume_restores_the_same_ids(admin, branches):
    code, files = branches
    karan = Customer.objects.visible().get(golden_fields__value="Karan Gill").id
    out = admin.post(f"/api/connectors/{code}/files/status/", {"ids": [files["south.csv"]], "status": "suspended"},
                     format="json")
    assert out.status_code == 200 and out.json()["changed"] == 1
    # Karan was only in south.csv; S1 falls back to north.csv's older value.
    assert visible_names() == ["Asha Rao", "Old Name", "Vikram Shetty"]
    assert Customer.objects.filter(id=karan).exists()  # hidden, not deleted

    admin.post(f"/api/connectors/{code}/files/status/", {"ids": [files["south.csv"]], "status": "active"},
               format="json")
    assert Customer.objects.visible().get(golden_fields__value="Karan Gill").id == karan

    admin.post(f"/api/connectors/{code}/files/status/", {"ids": list(files.values()), "status": "suspended"},
               format="json")
    assert visible_names() == []


def test_remove_shows_what_goes_then_deletes_only_that(admin, branches):
    code, files = branches
    karan = Customer.objects.visible().get(golden_fields__value="Karan Gill")
    Interaction.objects.create(customer=karan, channel="call", kind="query", summary="Asked about a cheque book",
                               outcome="resolved", created_by_name="x")
    preview = admin.get(f"/api/connectors/{code}/files/remove/?ids={files['south.csv']}").json()
    assert preview == {"files": 1, "records": 1, "customers": 1, "conversations": 1, "corrections": 0}
    assert admin.post(f"/api/connectors/{code}/files/remove/", {"ids": [files["south.csv"]]},
                      format="json").status_code == 400  # not confirmed
    done = admin.post(f"/api/connectors/{code}/files/remove/", {"ids": [files["south.csv"]], "confirm": True},
                      format="json")
    assert done.status_code == 200 and [f["name"] for f in done.json()["files"]] == ["north.csv"]
    assert not Customer.objects.filter(id=karan.id).exists() and not Interaction.objects.exists()
    assert visible_names() == ["Asha Rao", "Old Name", "Vikram Shetty"]  # S1 stays, from north.csv


def test_only_admins_manage_files(admin, branches):
    code, files = branches
    steward = User.objects.create_user("files.steward", password="Strong-pass-123")
    steward.groups.add(Group.objects.get(name="Data steward"))
    c = APIClient()
    c.force_authenticate(steward)
    assert c.get(f"/api/connectors/{code}/files/").status_code == 403
    assert c.post(f"/api/connectors/{code}/files/status/", {"ids": [files["north.csv"]], "status": "suspended"},
                  format="json").status_code == 403
