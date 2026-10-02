from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..auth import Principal, require
from ..db import get_db
from ..audit import write_audit
from ..worker_client import worker

router = APIRouter(prefix="/api/ad", tags=["active-directory"])

class PasswordBody(BaseModel):
    new_password: str = Field(min_length=12)
    must_change: bool = True

@router.get("/users")
async def users(q: str = Query(default=""), _: Principal = Depends(require("ad.read"))):
    return await worker.request("GET", "/ad/users", params={"q": q})

@router.get("/users/{identity}")
async def user(identity: str, _: Principal = Depends(require("ad.read"))):
    return await worker.request("GET", f"/ad/users/{identity}")

@router.post("/users/{identity}/unlock")
async def unlock(identity: str, principal: Principal = Depends(require("ad.unlock")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/ad/users/{identity}/unlock")
    write_audit(db, principal, "ad.user.unlock", identity)
    return result

@router.post("/users/{identity}/enable")
async def enable(identity: str, principal: Principal = Depends(require("ad.enable_disable")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/ad/users/{identity}/enable")
    write_audit(db, principal, "ad.user.enable", identity)
    return result

@router.post("/users/{identity}/disable")
async def disable(identity: str, principal: Principal = Depends(require("ad.enable_disable")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/ad/users/{identity}/disable")
    write_audit(db, principal, "ad.user.disable", identity)
    return result

@router.post("/users/{identity}/reset-password")
async def reset_password(identity: str, body: PasswordBody, principal: Principal = Depends(require("ad.password")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/ad/users/{identity}/reset-password", payload=body.model_dump())
    write_audit(db, principal, "ad.user.reset_password", identity, details={"must_change": body.must_change})
    return result

@router.get("/groups")
async def groups(_: Principal = Depends(require("group.read"))):
    return await worker.request("GET", "/ad/groups")

@router.get("/computers")
async def computers(_: Principal = Depends(require("computer.read"))):
    return await worker.request("GET", "/ad/computers")

@router.get("/ous")
async def ous(_: Principal = Depends(require("ou.read"))):
    return await worker.request("GET", "/ad/ous")
