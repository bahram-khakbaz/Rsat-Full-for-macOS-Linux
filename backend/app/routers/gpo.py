from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import audited, write_audit
from ..auth import Principal, require
from ..db import get_db
from ..worker_client import worker

router = APIRouter(prefix="/api/gpo", tags=["group-policy"])


async def _audited(db, principal, action, target, method, path, payload=None, details=None):
    return await audited(
        lambda: worker.request(method, path, payload=payload),
        write_audit,
        db,
        principal,
        action,
        target,
        details,
    )


class GpoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    comment: str = ""


class GpoLink(BaseModel):
    target: str
    enforced: bool = False
    enabled: bool = True
    order: int | None = Field(default=None, ge=1)


class GpoStatus(BaseModel):
    status: Literal[
        "AllSettingsEnabled",
        "UserSettingsDisabled",
        "ComputerSettingsDisabled",
        "AllSettingsDisabled",
    ]


class BackupBody(BaseModel):
    path: str = Field(min_length=3, max_length=1024)


class GpoPermission(BaseModel):
    trustee: str = Field(min_length=1, max_length=256)
    target_type: Literal["User", "Group", "Computer"] = "Group"
    permission: Literal["GpoRead", "GpoApply", "GpoEdit", "GpoEditDeleteModifySecurity"] = "GpoRead"
    replace: bool = False


@router.get("")
async def list_gpo(_: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", "/gpo")


@router.post("")
async def create_gpo(
    body: GpoCreate,
    principal: Principal = Depends(require("gpo.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "gpo.create",
        body.name,
        "POST",
        "/gpo",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.delete("/{gpo_id}")
async def delete_gpo(
    gpo_id: str, principal: Principal = Depends(require("gpo.write")), db: Session = Depends(get_db)
):
    return await _audited(
        db,
        principal,
        "gpo.delete",
        gpo_id,
        "DELETE",
        f"/gpo/{quote(gpo_id, safe='')}",
    )


@router.get("/links")
async def links(_: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", "/gpo/links")


@router.post("/{gpo_id}/link")
async def link(
    gpo_id: str,
    body: GpoLink,
    principal: Principal = Depends(require("gpo.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "gpo.link",
        gpo_id,
        "POST",
        f"/gpo/{quote(gpo_id, safe='')}/link",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/{gpo_id}/unlink")
async def unlink(
    gpo_id: str,
    body: GpoLink,
    principal: Principal = Depends(require("gpo.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "gpo.unlink",
        gpo_id,
        "POST",
        f"/gpo/{quote(gpo_id, safe='')}/unlink",
        payload=body.model_dump(),
        details={"target": body.target},
    )


@router.post("/{gpo_id}/status")
async def status(
    gpo_id: str,
    body: GpoStatus,
    principal: Principal = Depends(require("gpo.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "gpo.status",
        gpo_id,
        "POST",
        f"/gpo/{quote(gpo_id, safe='')}/status",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/{gpo_id}/backup")
async def backup(
    gpo_id: str,
    body: BackupBody,
    principal: Principal = Depends(require("gpo.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "gpo.backup",
        gpo_id,
        "POST",
        f"/gpo/{quote(gpo_id, safe='')}/backup",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.get("/{gpo_id}/report")
async def report(gpo_id: str, _: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", f"/gpo/{quote(gpo_id, safe='')}/report")


@router.get("/{gpo_id}/permissions")
async def permissions(gpo_id: str, _: Principal = Depends(require("gpo.read"))):
    return await worker.request("GET", f"/gpo/{quote(gpo_id, safe='')}/permissions")


@router.post("/{gpo_id}/permissions")
async def set_permission(
    gpo_id: str,
    body: GpoPermission,
    principal: Principal = Depends(require("gpo.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "gpo.permission.set",
        gpo_id,
        "POST",
        f"/gpo/{quote(gpo_id, safe='')}/permissions",
        payload=body.model_dump(),
        details=body.model_dump(),
    )
