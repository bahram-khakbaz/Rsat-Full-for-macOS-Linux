from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import write_audit
from ..auth import (
    LoginRequest,
    Principal,
    account_key,
    authenticate,
    bump_admin_token_version,
    clear_session_cookie,
    client_key,
    constant_time_equal,
    current_principal,
    hash_password,
    issue_token,
    permissions_for,
    set_session_cookie,
    throttle,
    verify_password,
)
from ..config import settings
from ..db import Operator, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# A single client may legitimately try several accounts; allow more attempts
# per client than per account before locking it out.
CLIENT_FAILURE_FACTOR = 4


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=256)


def profile(principal: Principal) -> dict:
    managed = (
        "environment"
        if constant_time_equal(principal.username, settings.admin_username)
        else "local"
    )
    return {
        "username": principal.username,
        "role": principal.role,
        "permissions": permissions_for(principal.role),
        "managed": managed,
    }


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    keys = (account_key(body.username), client_key(request))
    wait = max(throttle.retry_after(key) for key in keys)
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed sign-in attempts. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )
    attempt = Principal(username=body.username[:255], role="anonymous")
    result = authenticate(db, body.username, body.password)
    if result is None:
        throttle.failure(keys[0], settings.login_max_failures)
        throttle.failure(keys[1], settings.login_max_failures * CLIENT_FAILURE_FACTOR)
        write_audit(db, attempt, "auth.login", body.username[:255], status="failed")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    principal, token = result
    throttle.reset(keys[0])
    set_session_cookie(request, response, token)
    write_audit(db, principal, "auth.login", principal.username)
    return {"access_token": token, "token_type": "bearer", "user": profile(principal)}


@router.get("/me")
def me(principal: Principal = Depends(current_principal)):
    return profile(principal)


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


def _operator(db: Session, principal: Principal) -> Operator:
    operator = db.query(Operator).filter(Operator.username == principal.username).first()
    if operator is None:
        raise HTTPException(
            status_code=409,
            detail="This account is managed by the server environment (ADMIN_PASSWORD), "
            "not in the panel.",
        )
    return operator


@router.post("/password")
def change_password(
    body: PasswordChange,
    request: Request,
    response: Response,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    operator = _operator(db, principal)
    if not verify_password(body.current_password, operator.password_hash):
        write_audit(db, principal, "auth.password.change", principal.username, status="failed")
        raise HTTPException(status_code=403, detail="Current password is incorrect")
    operator.password_hash = hash_password(body.new_password)
    # Every other session ends; this one continues with a freshly issued token.
    operator.token_version += 1
    db.commit()
    token = issue_token(
        operator.username, operator.role, version=operator.token_version, subject_id=operator.id
    )
    set_session_cookie(request, response, token)
    write_audit(db, principal, "auth.password.change", principal.username)
    return {"ok": True}


@router.post("/revoke-sessions")
def revoke_sessions(
    response: Response,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    operator = db.query(Operator).filter(Operator.username == principal.username).first()
    if operator is not None:
        operator.token_version += 1
    elif constant_time_equal(principal.username, settings.admin_username):
        bump_admin_token_version(db)
    else:
        raise HTTPException(status_code=409, detail="This session cannot be revoked")
    db.commit()
    clear_session_cookie(response)
    write_audit(db, principal, "auth.sessions.revoke", principal.username)
    return {"ok": True}
