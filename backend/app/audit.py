import json
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .auth import Principal
from .db import AuditLog

SENSITIVE_KEYS = {"password", "new_password", "current_password", "secret", "token"}


def redact(value):
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in SENSITIVE_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def write_audit(
    db: Session,
    principal: Principal,
    action: str,
    target: str = "",
    status: str = "success",
    details=None,
):
    item = AuditLog(
        actor=principal.username,
        role=principal.role,
        action=action,
        target=target[:255],
        status=status,
        details=json.dumps(redact(details or {}), ensure_ascii=False, default=str),
    )
    db.add(item)
    db.commit()


async def audited(
    call: Callable[[], Awaitable],
    write: Callable,
    db: Session,
    principal: Principal,
    action: str,
    target: str = "",
    details: dict | None = None,
):
    """Run a privileged operation and record its outcome, including failures.

    Rejected or failed attempts are part of the security record: they are stored
    with status ``failed`` and the error returned to the operator. Operations
    answered by demo fixtures are stored as ``demo`` so they are never mistaken
    for real directory changes.
    """
    try:
        result = await call()
    except HTTPException as exc:
        failure = {
            **(details or {}),
            "error": str(exc.detail)[:500],
            "http_status": exc.status_code,
        }
        write(db, principal, action, target, status="failed", details=failure)
        raise
    simulated = isinstance(result, dict) and result.get("demo") is True
    write(db, principal, action, target, status="demo" if simulated else "success", details=details)
    return result
