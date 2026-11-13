"""Encryption of credentials stored in the local database.

Stored values keep the ``enc:`` prefix followed by a Fernet token. The primary
key comes from ``ENCRYPTION_KEY`` (HKDF-SHA256); when that is not configured the
legacy key derived from ``JWT_SECRET`` remains the primary key, so existing
installations keep working unchanged. Former keys stay valid for decryption and
values are re-encrypted under the primary key at start-up.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import settings

log = logging.getLogger(__name__)
PREFIX = "enc:"
_HKDF_INFO = b"rsat-credential-store-v1"


def _legacy_fernet() -> Fernet:
    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _derived_fernet(secret: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(
        secret.encode("utf-8")
    )
    return Fernet(base64.urlsafe_b64encode(key))


def _primary() -> Fernet:
    if settings.encryption_key:
        return _derived_fernet(settings.encryption_key)
    return _legacy_fernet()


def _keyring() -> MultiFernet:
    keys = [_primary()]
    keys += [
        _derived_fernet(value.strip())
        for value in settings.encryption_key_previous.split(",")
        if value.strip()
    ]
    if settings.encryption_key:
        keys.append(_legacy_fernet())
    return MultiFernet(keys)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return PREFIX + _primary().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith("vault-agent:"):
        from .vault_agent import read

        return read(value)
    if not value.startswith(PREFIX):
        return value
    try:
        return _keyring().decrypt(value[len(PREFIX) :].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        # Callers treat an empty value as "credential unavailable"; make the
        # cause visible to the operator instead of failing silently.
        log.warning(
            "A stored credential could not be decrypted with the configured keys. "
            "Check JWT_SECRET / ENCRYPTION_KEY, or save the credential again."
        )
        return ""


def needs_rotation(value: str) -> bool:
    """True when a locally encrypted value is not protected by the primary key."""
    if not value or not value.startswith(PREFIX):
        return False
    try:
        _primary().decrypt(value[len(PREFIX) :].encode("ascii"))
        return False
    except (InvalidToken, ValueError):
        return True


def rotate_secret(value: str) -> str:
    """Re-encrypt a stored value under the primary key; unreadable values are kept."""
    if not needs_rotation(value):
        return value
    try:
        token = _keyring().rotate(value[len(PREFIX) :].encode("ascii"))
    except (InvalidToken, ValueError):
        return value
    return PREFIX + token.decode("ascii")


def store_credential(password: str, vault_key: str | None, owner: str, previous: str = "") -> str:
    from fastapi import HTTPException

    from .vault_agent import reference

    if password and vault_key:
        raise HTTPException(422, "Provide either a local password or a Vault Agent key, not both")
    if vault_key:
        return reference(owner, vault_key)
    return encrypt_secret(password) if password else previous
