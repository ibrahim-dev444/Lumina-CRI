"""Shared test setup."""

import pytest

from security import crypto

# A throwaway key used only by the test suite. Real keys live in each environment's .env.
TEST_FIELD_KEY = "q2Y0rRk9lW8m2kq3V5yXyvNn3D7m8f8x9oQqY0w1Z2E="


@pytest.fixture(autouse=True)
def field_encryption_key(settings):
    settings.FIELD_ENCRYPTION_KEY = TEST_FIELD_KEY
    for cached in (crypto._key_material, crypto._fernet, crypto._hash_key):
        cached.cache_clear()
    yield
    for cached in (crypto._key_material, crypto._fernet, crypto._hash_key):
        cached.cache_clear()
