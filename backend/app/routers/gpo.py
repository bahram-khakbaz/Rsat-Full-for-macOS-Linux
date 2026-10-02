from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..auth import Principal, require
from ..db import get_db
from ..audit import write_audit
from ..worker_client import worker

router = APIRouter(prefix="/api/gpo", tags=["group-policy"])

class GpoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    comment: str = ""

class GpoLink(BaseModel):
    target: str
    enforced: bool = False
    enabled: bool = True
    order: int | None = Field(default=None, ge=1)

class GpoStatus(BaseModel):
    status: Literal["AllSettingsEnabled","UserSettingsDisabled","ComputerSettingsDisabled","AllSettingsDisabled"]

class BackupBody(BaseModel):
    path: str = Field(min_length=3, max_length=1024)

class GpoPermission(BaseModel):
    trustee: str = Field(min_length=1, max_length=256)
    target_type: Literal["User","Group","Computer"] = "Group"
    permission: Literal["GpoRead","GpoApply","GpoEdit","GpoEditDeleteModifySecurity"] = "GpoRead"
    replace: bool = False

@router.get("")
async def list_gpo(_: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", "/gpo")

@router.post("")
async def create_gpo(body: GpoCreate, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/gpo", payload=body.model_dump())
    write_audit(db, principal, "gpo.create", body.name, details=body.model_dump())
    return result

@router.delete("/{gpo_id}")
async def delete_gpo(gpo_id: str, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)):
    result = await worker.request("DELETE", f"/gpo/{gpo_id}")
    write_audit(db, principal, "gpo.delete", gpo_id)
    return result

@router.get("/links")
async def links(_: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", "/gpo/links")

@router.post("/{gpo_id}/link")
async def link(gpo_id: str, body: GpoLink, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/gpo/{gpo_id}/link", payload=body.model_dump())
    write_audit(db, principal, "gpo.link", gpo_id, details=body.model_dump())
    return result

@router.post("/{gpo_id}/unlink")
async def unlink(gpo_id: str, body: GpoLink, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/gpo/{gpo_id}/unlink", payload=body.model_dump())
    write_audit(db, principal, "gpo.unlink", gpo_id, details={"target": body.target})
    return result

@router.post("/{gpo_id}/status")
async def status(gpo_id: str, body: GpoStatus, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/gpo/{gpo_id}/status", payload=body.model_dump())
    write_audit(db, principal, "gpo.status", gpo_id, details=body.model_dump())
    return result

@router.post("/{gpo_id}/backup")
async def backup(gpo_id: str, body: BackupBody, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/gpo/{gpo_id}/backup", payload=body.model_dump())
    write_audit(db, principal, "gpo.backup", gpo_id, details=body.model_dump())
    return result

@router.get("/{gpo_id}/report")
async def report(gpo_id: str, _: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", f"/gpo/{gpo_id}/report")

@router.get("/{gpo_id}/permissions")
async def permissions(gpo_id: str, _: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", f"/gpo/{gpo_id}/permissions")

@router.post("/{gpo_id}/permissions")
async def set_permission(gpo_id: str, body: GpoPermission, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/gpo/{gpo_id}/permissions", payload=body.model_dump())
    write_audit(db, principal, "gpo.permission.set", gpo_id, details=body.model_dump())
    return result
