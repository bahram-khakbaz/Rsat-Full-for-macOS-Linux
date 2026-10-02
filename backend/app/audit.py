import json
from sqlalchemy.orm import Session
from .auth import Principal
from .db import AuditLog

SENSITIVE_KEYS = {"password", "new_password", "secret", "token"}

def redact(value):
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in SENSITIVE_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value

def write_audit(db: Session, principal: Principal, action: str, target: str = "", status: str = "success", details=None):
    item = AuditLog(actor=principal.username, role=principal.role, action=action, target=target, status=status,
                    details=json.dumps(redact(details or {}), ensure_ascii=False))
    db.add(item)
    db.commit()
