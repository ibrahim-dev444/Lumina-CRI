from .base import BaseConnector
from .generic import _when

# Fields a pushed record may carry: Lumina's own names, plus "id" (required) and "updated_at" (optional).
PUSH_FIELDS = (
    "name", "father_name", "dob", "gender", "pan", "aadhaar", "ckyc", "mobile", "email", "address",
    "perm_address", "occupation", "income", "country", "residency",
)


class PushConnector(BaseConnector):
    """Records sent to the push API already use Lumina's field names, so renaming is one-to-one."""

    source_code = None
    sensitive_columns = {"pan": "pan", "aadhaar": "aadhaar", "ckyc": "ckyc"}

    def fetch(self):
        raise NotImplementedError("Push sources are not read; their records arrive at the ingest endpoint.")

    def record_id(self, raw):
        value = raw.get("id")
        return str(value).strip() if value not in (None, "") else ""

    def to_standard(self, raw):
        std = {field: raw.get(field) for field in PUSH_FIELDS if field in raw}
        std["source_updated_at"] = _when(raw.get("updated_at"))
        return std
