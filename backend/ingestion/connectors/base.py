class BaseConnector:
    """Template every connector follows.

    A connector knows how to talk to ONE source system. It does two jobs:
      fetch()        read raw rows from that system, exactly as they are
      to_standard()  rename that system's columns to Lumina's standard fields

    Cleaning, saving and logging are the same for every source, so they live in
    ingestion/sync.py, not here.
    """

    source_code = None  # must match Source.code in the database, e.g. "flexcube"

    # Raw columns holding identity numbers, mapped to the standard field they feed. Their values are
    # protected before the raw copy is saved: PAN and CKYC encrypted, Aadhaar cut to the last 4 digits.
    sensitive_columns = {}

    def fetch(self):
        """Return a list of dicts, one per customer row, with the source's own column names."""
        raise NotImplementedError

    def record_id(self, raw):
        """Return the customer's ID inside the source system."""
        raise NotImplementedError

    def to_standard(self, raw):
        """Return a dict with Lumina's standard keys (see mdm.models.FIELDS) plus source_updated_at.
        Keys the source does not have can be left out."""
        raise NotImplementedError
