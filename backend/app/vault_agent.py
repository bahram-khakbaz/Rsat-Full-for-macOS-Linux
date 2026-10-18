"""Read short-lived Vault Agent deliveries; no Vault token enters RSAT."""
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import stat

from fastapi import HTTPException
from .config import settings

PREFIX = "vault-agent:v1:"
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def namespace(owner):
    return hashlib.sha256(owner.encode("utf-8")).hexdigest()


def reference(owner, key):
    if not settings.vault_credential_dir:
        raise HTTPException(422, "Vault Agent delivery is not configured on this backend")
    if not KEY.fullmatch(key):
        raise HTTPException(422, "Vault key must use letters, digits, underscores or hyphens")
    return PREFIX + namespace(owner) + ":" + key


def metadata(value):
    if value.startswith(PREFIX):
        parts = value[len(PREFIX):].split(":")
        if len(parts) == 2 and re.fullmatch(r"[a-f0-9]{64}", parts[0]) and KEY.fullmatch(parts[1]):
            return {"credential_source": "vault-agent", "vault_key": parts[1]}
    return {"credential_source": "local", "vault_key": ""}


def read(value):
    """Bounded, no-symlink directory traversal with freshness validation.

    Agent writes JSON atomically. Read every use so rotations need no DB update.
    Errors never include the delivery contents, filename or operating-system error.
    """
    handles = []
    try:
        if not settings.vault_credential_dir or not value.startswith(PREFIX):
            raise ValueError()
        owner, key = value[len(PREFIX):].split(":")
        if not re.fullmatch(r"[a-f0-9]{64}", owner) or not KEY.fullmatch(key):
            raise ValueError()
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
        root = os.open(settings.vault_credential_dir, flags); handles.append(root)
        directory = os.open(owner, flags, dir_fd=root); handles.append(directory)
        if any(os.fstat(handle).st_mode & 0o022 for handle in (root, directory)):
            raise ValueError()
        fd = os.open(key + ".json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        handles.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 16384:
            raise ValueError()
        raw = os.read(fd, 16385)
        if len(raw) > 16384:
            raise ValueError()
        document = json.loads(raw)
        delivered = datetime.fromisoformat(document["rendered_at"].replace("Z", "+00:00"))
        if delivered.tzinfo is None:
            raise ValueError()
        age = (datetime.now(timezone.utc) - delivered).total_seconds()
        password = document["password"]
        if not -30 <= age <= settings.vault_max_age_seconds or not isinstance(password, str) or not 1 <= len(password) <= 4096:
            raise ValueError()
        return password
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(503, "Vault Agent credential delivery is missing, invalid or stale; no local fallback was used") from None
    finally:
        for fd in reversed(handles):
            os.close(fd)
