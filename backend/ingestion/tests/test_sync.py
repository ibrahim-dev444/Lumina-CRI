import pytest

from ingestion.connectors.flexcube import FlexcubeConnector
from ingestion.models import RawRecord, SourceRecord
from ingestion.sync import sync_source
from sources.models import Source

from .test_flexcube import ROW


@pytest.fixture
def fake_flexcube(monkeypatch):
    """Replace the real database read with one in-memory row, so the test needs no FLEXCUBE DB."""
    rows = [dict(ROW)]
    monkeypatch.setattr(FlexcubeConnector, "fetch", lambda self: [dict(r) for r in rows])
    return rows


@pytest.mark.django_db
def test_first_sync_creates_records(fake_flexcube):
    result = sync_source("flexcube")

    assert (result.fetched, result.created, result.updated) == (1, 1, 0)
    record = SourceRecord.objects.get(source__code="flexcube", source_record_id="FX0000101")
    assert record.name == "Suresh Kumar"
    assert record.mobile == "9822104521"
    assert RawRecord.objects.get().payload["MOB_NO"] == "+91 98221 04521"  # raw copy kept as received
    assert Source.objects.get(code="flexcube").last_synced_at is not None


@pytest.mark.django_db
def test_second_sync_updates_instead_of_duplicating(fake_flexcube):
    sync_source("flexcube")
    fake_flexcube[0]["MOB_NO"] = "9822107788"

    result = sync_source("flexcube")

    assert (result.created, result.updated) == (0, 1)
    assert SourceRecord.objects.count() == 1
    assert SourceRecord.objects.get().mobile == "9822107788"
    assert RawRecord.objects.count() == 2  # every pull is kept


@pytest.mark.django_db
def test_disabled_source_is_refused(fake_flexcube):
    Source.objects.filter(code="flexcube").update(enabled=False)
    with pytest.raises(ValueError, match="disabled"):
        sync_source("flexcube")
