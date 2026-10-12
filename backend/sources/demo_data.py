from pathlib import Path

from django.conf import settings
from django.db import connection


def demo_data_dir() -> Path:
    """This organization's synthetic demo data: fake_sources/<schema>/ (e.g. fake_sources/axis/).

    Connectors call this while a request or command runs inside one organization's schema, so each bank
    only ever reads its own files.
    """
    schema = connection.schema_name
    if schema == "public":
        raise RuntimeError("Demo data belongs to an organization; this code ran outside one.")
    return Path(settings.DEMO_DATA_DIR) / schema
