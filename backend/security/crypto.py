"""Protection for the most sensitive identifiers (PAN, CKYC number).

- encrypt / decrypt: the value is stored encrypted, so a database copy or backup does not reveal it.
- fingerprint: a keyed hash (HMAC-SHA256). The same PAN always gives the same fingerprint, so records can
  be matched and compared without decrypting anything. Without the key it cannot be reversed or guessed.

Keys come from FIELD_ENCRYPTION_KEY in .env. In development, if it is missing, a key is derived from
DJANGO_SECRET_KEY so the project still runs; production must set its own key and keep it out of git.
"""

import base64
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _key_material():
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key:
        if not settings.DEBUG:
            raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY must be set when DJANGO_DEBUG is false.")
        key = base64.urlsafe_b64encode(hashlib.sha256(("dev-field-key:" + settings.SECRET_KEY).encode()).digest())
        key = key.decode()
    return key


@lru_cache(maxsize=1)
def _fernet():
    return Fernet(_key_material().encode())


@lru_cache(maxsize=1)
def _hash_key():
    # A separate key for fingerprints, derived from the same secret but for a different purpose.
    return hashlib.sha256(("fingerprint:" + _key_material()).encode()).digest()


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(value):
    if not value or is_encrypted(value):
        return value or ""
    return PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt(value):
    if not is_encrypted(value):
        return value or ""
    try:
        return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken:
        return ""  # wrong key: show nothing rather than garbage


def fingerprint(plain):
    if not plain:
        return ""
    return hmac.new(_hash_key(), plain.encode(), hashlib.sha256).hexdigest()
