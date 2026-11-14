"""Panel authentication, sessions and role-based authorization.

Sessions are signed JWTs delivered in an httpOnly, SameSite=Strict cookie (a
bearer header is still accepted for API clients). Tokens issued at sign-in carry
a version that is checked against the database on every request, so disabling an
operator, changing a password or "sign out everywhere" takes effect immediately.
"""

import base64
import hashlib
import hmac
import secrets
import threading
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .config import settings
from .db import Operator, SystemSetting, get_db

security = HTTPBearer(auto_error=False)

SESSION_COOKIE = "rsat_session"
ADMIN_VERSION_KEY = "admin_token_version"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

ROLE_PERMISSIONS = {
    "admin": {"*"},
    "helpdesk": {
        "domain.read",
        "ad.read",
        "ad.create",
        "ad.update",
        "ad.unlock",
        "ad.password",
        "ad.enable_disable",
        "group.read",
        "group.membership",
        "computer.read",
        "ou.read",
        "audit.read",
    },
    "network": {
        "ipam.read",
        "ipam.write",
        "ssh.read",
        "ssh.write",
        "ssh.connect",
        "sftp.read",
        "sftp.write",
        "domain.read",
        "dns.read",
        "dns.write",
        "dhcp.read",
        "dhcp.write",
        "audit.read",
    },
    "gpo_admin": {"domain.read", "ad.read", "ou.read", "gpo.read", "gpo.write", "audit.read"},
    "auditor": {
        "domain.read",
        "ad.read",
        "group.read",
        "computer.read",
        "ou.read",
        "dns.read",
        "dhcp.read",
        "gpo.read",
        "audit.read",
    },
    "read_only": {
        "domain.read",
        "ad.read",
        "group.read",
        "computer.read",
        "ou.read",
        "dns.read",
        "dhcp.read",
        "gpo.read",
    },
}


class Principal(BaseModel):
    username: str
    role: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


def permissions_for(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))


# --- Password hashing -------------------------------------------------------

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**15, 8, 1
_SCRYPT_MAXMEM = 128 * 1024 * 1024


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=_SCRYPT_MAXMEM, dklen=32
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return "$".join(
        [
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest, validate=True)
        actual = _scrypt(password, base64.b64decode(salt, validate=True), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verified against when the account does not exist, so response time does not
# reveal which usernames are registered.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def constant_time_equal(left: str, right: str) -> bool:
    """Compare text safely; ``secrets.compare_digest`` rejects non-ASCII ``str``."""
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


# --- Sign-in throttling -----------------------------------------------------


class LoginThrottle:
    """In-memory lockout after repeated failures, keyed by account and by client."""

    def __init__(self, max_entries: int = 10_000):
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[int, float]] = {}  # key -> (failures, locked_until)
        self._max_entries = max_entries

    def retry_after(self, key: str) -> int:
        with self._lock:
            failures, locked_until = self._entries.get(key, (0, 0.0))
            remaining = locked_until - time.monotonic()
            return int(remaining) + 1 if remaining > 0 else 0

    def failure(self, key: str, limit: int) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._entries) >= self._max_entries:
                self._entries = {k: v for k, v in self._entries.items() if v[1] > now}
            failures, locked_until = self._entries.get(key, (0, 0.0))
            failures += 1
            if failures >= limit:
                # Each further failure after the limit doubles the lockout, up to 8x.
                factor = min(2 ** (failures - limit), 8)
                locked_until = now + settings.login_lockout_seconds * factor
            self._entries[key] = (failures, locked_until)

    def reset(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


throttle = LoginThrottle()


def account_key(username: str) -> str:
    return "user:" + username.strip().casefold()


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-real-ip", "")
    return "ip:" + (forwarded or (request.client.host if request.client else "unknown"))


# --- Tokens -----------------------------------------------------------------


def issue_token(
    username: str,
    role: str = "admin",
    *,
    version: int | None = None,
    subject_id: int | None = None,
) -> str:
    """Sign a session token.

    Sign-in passes ``version``/``subject_id`` so the session can be revoked.
    Tokens without a version are only minted by trusted server-side code.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_exp_minutes),
    }
    if version is not None:
        payload["ver"] = version
        payload["uid"] = subject_id or 0
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def admin_token_version(db: Session) -> int:
    row = db.query(SystemSetting).filter(SystemSetting.key == ADMIN_VERSION_KEY).first()
    try:
        return int(row.value) if row else 1
    except ValueError:
        return 1


def bump_admin_token_version(db: Session) -> int:
    row = db.query(SystemSetting).filter(SystemSetting.key == ADMIN_VERSION_KEY).first()
    version = admin_token_version(db) + 1
    if row:
        row.value = str(version)
    else:
        db.add(SystemSetting(key=ADMIN_VERSION_KEY, value=str(version)))
    return version


def authenticate(db: Session, username: str, password: str) -> tuple[Principal, str] | None:
    """Return the principal and a revocable session token, or None."""
    if constant_time_equal(username, settings.admin_username):
        if constant_time_equal(password, settings.admin_password):
            token = issue_token(username, "admin", version=admin_token_version(db), subject_id=0)
            return Principal(username=username, role="admin"), token
        return None
    operator = db.query(Operator).filter(Operator.username == username).first()
    if operator is None or operator.disabled:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, operator.password_hash):
        return None
    operator.last_login_at = datetime.now(UTC)
    db.commit()
    token = issue_token(
        operator.username, operator.role, version=operator.token_version, subject_id=operator.id
    )
    return Principal(username=operator.username, role=operator.role), token


def set_session_cookie(request: Request, response: Response, token: str) -> None:
    secure = settings.cookie_secure
    if secure is None:
        secure = (
            request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.jwt_exp_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/api",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/api", httponly=True, samesite="strict")


def _same_origin(request: Request) -> bool:
    """Reject cross-site state changes made with the ambient session cookie."""
    origin = request.headers.get("origin")
    if origin:
        if origin in settings.cors_list:
            return True
        return urlparse(origin).netloc == request.headers.get("host")
    return request.headers.get("sec-fetch-site") in ("same-origin", "none")


def _session_claims(db: Session, claims: dict) -> Principal:
    """Validate a revocable session against the current account state."""
    invalid = HTTPException(status_code=401, detail="Session is no longer valid. Sign in again.")
    if claims.get("uid") == 0:
        if not constant_time_equal(str(claims["sub"]), settings.admin_username):
            raise invalid
        if claims["ver"] != admin_token_version(db):
            raise invalid
        return Principal(username=claims["sub"], role="admin")
    subject_id = claims.get("uid")
    operator = db.get(Operator, subject_id) if isinstance(subject_id, int) else None
    if (
        operator is None
        or operator.disabled
        or operator.username != claims["sub"]
        or operator.token_version != claims["ver"]
    ):
        raise invalid
    # The stored role wins, so a role change applies to sessions already open.
    return Principal(username=operator.username, role=operator.role)


def current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Principal:
    if credentials:
        token = credentials.credentials
    else:
        token = request.cookies.get(SESSION_COOKIE)
        if token and request.method not in SAFE_METHODS and not _same_origin(request):
            raise HTTPException(status_code=403, detail="Cross-site request blocked")
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        username = claims["sub"]
    except (jwt.PyJWTError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    if "ver" in claims:
        return _session_claims(db, claims)
    return Principal(username=username, role=claims.get("role", "read_only"))


def require(permission: str):
    def dep(principal: Principal = Depends(current_principal)) -> Principal:
        perms = ROLE_PERMISSIONS.get(principal.role, set())
        if "*" not in perms and permission not in perms:
            raise HTTPException(status_code=403, detail="Insufficient permission")
        return principal

    return dep
