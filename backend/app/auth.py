from datetime import datetime, timedelta, timezone
import secrets
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from .config import settings

security = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS = {
    "admin": {"*"},
    "helpdesk": {"ad.read", "ad.unlock", "ad.password", "ad.enable_disable", "group.read", "audit.read"},
    "network": {"dns.read", "dns.write", "dhcp.read", "dhcp.write", "audit.read"},
    "auditor": {"ad.read", "group.read", "computer.read", "ou.read", "dns.read", "dhcp.read", "gpo.read", "audit.read"},
    "read_only": {"ad.read", "group.read", "computer.read", "ou.read", "dns.read", "dhcp.read", "gpo.read"},
}

class Principal(BaseModel):
    username: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str

def issue_token(username: str, role: str = "admin") -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": username, "role": role, "iat": now, "exp": now + timedelta(minutes=settings.jwt_exp_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def authenticate_local(username: str, password: str) -> Principal | None:
    if secrets.compare_digest(username, settings.admin_username) and secrets.compare_digest(password, settings.admin_password):
        return Principal(username=username, role="admin")
    return None

def current_principal(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> Principal:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        data = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        return Principal(username=data["sub"], role=data.get("role", "read_only"))
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

def require(permission: str):
    def dep(principal: Principal = Depends(current_principal)) -> Principal:
        perms = ROLE_PERMISSIONS.get(principal.role, set())
        if "*" not in perms and permission not in perms:
            raise HTTPException(status_code=403, detail="Insufficient permission")
        return principal
    return dep
