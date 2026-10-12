"""Checking an organization's uploaded logo before it is stored and shown to its staff."""

import base64
import binascii
import re

MAX_LOGO_BYTES = 256 * 1024

# Only plain picture formats. SVG is refused: it is a document that can carry scripts and links.
SIGNATURES = {
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}
DATA_URL = re.compile(r"^data:(image/[a-z+]+);base64,([A-Za-z0-9+/=\s]+)$")


class LogoError(ValueError):
    pass


def clean_logo(value):
    """Returns a safe data:image/... URL, or "" to remove the logo. Raises LogoError for anything else."""
    value = (value or "").strip()
    if not value:
        return ""
    match = DATA_URL.match(value)
    if not match:
        raise LogoError("Upload a PNG, JPEG or WebP image.")
    content_type, encoded = match.groups()
    if content_type not in SIGNATURES:
        raise LogoError("Upload a PNG, JPEG or WebP image. SVG files are not accepted.")
    try:
        data = base64.b64decode(encoded, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise LogoError("The image could not be read.") from exc
    if len(data) > MAX_LOGO_BYTES:
        raise LogoError("The logo must be 256 KB or smaller.")
    if not SIGNATURES[content_type](data):
        raise LogoError("The file is not the kind of image its name says.")
    return f"data:{content_type};base64,{base64.b64encode(data).decode()}"
