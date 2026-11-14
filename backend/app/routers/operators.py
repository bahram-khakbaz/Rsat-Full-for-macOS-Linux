"""Panel operators: local accounts that sign in to RSAT with an assigned role."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import (
    ROLE_PERMISSIONS,
    Principal,
    account_key,
    constant_time_equal,
    hash_password,
    permissions_for,
    require,
    throttle,
)
from ..config import settings
from ..db import Operator, get_db

router = APIRouter(prefix="/api/operators", tags=["operators"])
Role = Literal["admin", "helpdesk", "network", "gpo_admin", "auditor", "read_only"]
PERMISSION = "operators.manage"


class OperatorCreate(BaseModel):
    username: str
    password: str = Field(min_length=12, max_length=256)
    role: Role = "read_only"

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip()
        if not 3 <= len(value) <= 64 or not all(c.isalnum() or c in "._@-" for c in value):
            raise ValueError("Use 3-64 letters, digits, dots, underscores, hyphens or @")
        return value


class OperatorPatch(BaseModel):
    model_config = {"extra": "forbid"}
    role: Role | None = None
    disabled: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)


def public(row: Operator) -> dict:
    return {
        "id": row.id,
        "username": row.username,
        "role": row.role,
        "disabled": row.disabled,
        "locked": throttle.retry_after(account_key(row.username)) > 0,
        "created_at": row.created_at,
        "last_login_at": row.last_login_at,
    }


def found(db: Session, identity: int) -> Operator:
    row = db.get(Operator, identity)
    if row is None:
        raise HTTPException(status_code=404, detail="Operator not found")
    return row


@router.get("")
def operators(_: Principal = Depends(require(PERMISSION)), db: Session = Depends(get_db)):
    return [public(row) for row in db.query(Operator).order_by(Operator.username).all()]


@router.get("/roles")
def roles(_: Principal = Depends(require(PERMISSION))):
    return {role: permissions_for(role) for role in ROLE_PERMISSIONS}


@router.post("")
def create(
    body: OperatorCreate,
    principal: Principal = Depends(require(PERMISSION)),
    db: Session = Depends(get_db),
):
    if constant_time_equal(body.username.casefold(), settings.admin_username.casefold()):
        raise HTTPException(status_code=409, detail="This name is reserved for the server admin")
    exists = db.query(Operator).filter(Operator.username == body.username).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="An operator with this name already exists")
    row = Operator(
        username=body.username, password_hash=hash_password(body.password), role=body.role
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, principal, "operator.create", row.username, details={"role": row.role})
    return public(row)


@router.patch("/{identity}")
def update(
    identity: int,
    body: OperatorPatch,
    principal: Principal = Depends(require(PERMISSION)),
    db: Session = Depends(get_db),
):
    row = found(db, identity)
    changes = {}
    if body.role is not None and body.role != row.role:
        row.role = body.role
        changes["role"] = body.role
    if body.disabled is not None and body.disabled != row.disabled:
        row.disabled = body.disabled
        changes["disabled"] = body.disabled
        row.token_version += 1
    if body.password is not None:
        row.password_hash = hash_password(body.password)
        row.token_version += 1
        changes["password_reset"] = True
    db.commit()
    db.refresh(row)
    write_audit(db, principal, "operator.update", row.username, details=changes)
    return public(row)


@router.post("/{identity}/unlock")
def unlock(
    identity: int,
    principal: Principal = Depends(require(PERMISSION)),
    db: Session = Depends(get_db),
):
    row = found(db, identity)
    throttle.reset(account_key(row.username))
    write_audit(db, principal, "operator.unlock", row.username)
    return public(row)


@router.delete("/{identity}")
def delete(
    identity: int,
    principal: Principal = Depends(require(PERMISSION)),
    db: Session = Depends(get_db),
):
    row = found(db, identity)
    username = row.username
    db.delete(row)
    db.commit()
    throttle.reset(account_key(username))
    write_audit(db, principal, "operator.delete", username)
    return {"ok": True}
