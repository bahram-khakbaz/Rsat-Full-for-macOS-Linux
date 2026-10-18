import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from .config import settings

def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return "enc:" + _fernet().encrypt(value.encode("utf-8")).decode("ascii")

def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    if value.startswith("vault-agent:"):
        from .vault_agent import read
        return read(value)
    if not value.startswith("enc:"):
        return value
    try:
        return _fernet().decrypt(value[4:].encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""

def store_credential(password: str, vault_key: str | None, owner: str, previous: str = "") -> str:
    from fastapi import HTTPException
    from .vault_agent import reference
    if password and vault_key:
        raise HTTPException(422, "Provide either a local password or a Vault Agent key, not both")
    if vault_key:
        return reference(owner, vault_key)
    return encrypt_secret(password) if password else previous
