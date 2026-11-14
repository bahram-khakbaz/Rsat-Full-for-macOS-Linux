import re
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel, Field, StrictBool, model_validator
from sqlalchemy.orm import Session

from ..audit import audited, write_audit
from ..auth import Principal, require
from ..db import get_db
from ..worker_client import worker

router = APIRouter(prefix="/api/ad", tags=["active-directory"])


def seg(value: str) -> str:
    """Encode one path segment so identities cannot alter the connector route."""
    return quote(value, safe="")


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


class PasswordBody(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)
    must_change: bool = True


class UserCreate(BaseModel):
    sam_account_name: str = Field(min_length=1, max_length=64)
    given_name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    email: str = ""
    department: str = ""
    title: str = ""
    company: str = ""
    manager: str = ""
    ou: str
    password: str = Field(min_length=8, max_length=256)
    enabled: bool = True
    must_change: bool = True


class UserPatch(BaseModel):
    display_name: str | None = None
    email: str | None = None
    department: str | None = None
    title: str | None = None
    company: str | None = None
    manager: str | None = None
    mobile: str | None = None


class AccountOptions(BaseModel):
    model_config = {"extra": "forbid"}
    password_never_expires: StrictBool | None = None
    change_password_at_logon: StrictBool | None = None
    smartcard_required: StrictBool | None = None
    sensitive_not_delegated: StrictBool | None = None
    account_never_expires: StrictBool | None = None
    account_expires: AwareDatetime | None = None
    logon_workstations: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def consistent(self):
        if self.password_never_expires and self.change_password_at_logon:
            raise ValueError("Password never expires conflicts with change password at next logon")
        if self.account_never_expires and self.account_expires:
            raise ValueError("Choose account never expires OR an expiration date")
        if self.account_never_expires is False and self.account_expires is None:
            raise ValueError("An expiration date with a timezone is required")
        if self.logon_workstations is not None:
            if self.logon_workstations and not re.fullmatch(
                r"[A-Za-z0-9_.-]+(?:,[A-Za-z0-9_.-]+)*", self.logon_workstations
            ):
                raise ValueError("Use comma-separated workstation names")
        return self


class MoveBody(BaseModel):
    target_ou: str = Field(min_length=3, max_length=1024)


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scope: Literal["DomainLocal", "Global", "Universal"] = "Global"
    category: Literal["Security", "Distribution"] = "Security"
    path: str
    description: str = ""


class MemberBody(BaseModel):
    member: str = Field(min_length=1, max_length=512)


class OUCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    path: str
    protected: bool = True


class OUDelete(BaseModel):
    dn: str
    recursive: bool = False


class RestoreBody(BaseModel):
    object_guid: str = Field(min_length=36, max_length=36)
    target_path: str = ""


@router.get("/users")
async def users(
    q: str = Query(default="", max_length=80),
    page_size: int | None = Query(default=None, ge=1, le=100),
    cursor: str = Query(default="", max_length=4096),
    _: Principal = Depends(require("ad.read")),
):
    return await worker.request(
        "GET", "/ad/users", params={"q": q, "page_size": page_size, "cursor": cursor}
    )


@router.post("/users")
async def create_user(
    body: UserCreate,
    principal: Principal = Depends(require("ad.create")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.user.create",
        body.sam_account_name,
        "POST",
        "/ad/users",
        payload=body.model_dump(),
        details=body.model_dump(exclude={"password"}),
    )


@router.get("/users/{identity}")
async def user(identity: str, _: Principal = Depends(require("ad.read"))):
    return await worker.request("GET", f"/ad/users/{seg(identity)}")


@router.patch("/users/{identity}/account-options")
async def account_options(
    identity: str,
    body: AccountOptions,
    principal: Principal = Depends(require("ad.update")),
    db: Session = Depends(get_db),
):
    payload = body.model_dump(exclude_none=True, mode="json")
    return await _audited(
        db,
        principal,
        "ad.user.account_options",
        identity,
        "PATCH",
        f"/ad/users/{seg(identity)}/account-options",
        payload=payload,
        details=payload,
    )


@router.patch("/users/{identity}")
async def update_user(
    identity: str,
    body: UserPatch,
    principal: Principal = Depends(require("ad.update")),
    db: Session = Depends(get_db),
):
    payload = body.model_dump(exclude_none=True)
    return await _audited(
        db,
        principal,
        "ad.user.update",
        identity,
        "PATCH",
        f"/ad/users/{seg(identity)}",
        payload=payload,
        details=payload,
    )


@router.delete("/users/{identity}")
async def delete_user(
    identity: str,
    principal: Principal = Depends(require("ad.delete")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.user.delete",
        identity,
        "DELETE",
        f"/ad/users/{seg(identity)}",
    )


@router.post("/users/{identity}/unlock")
async def unlock(
    identity: str,
    principal: Principal = Depends(require("ad.unlock")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.user.unlock",
        identity,
        "POST",
        f"/ad/users/{seg(identity)}/unlock",
    )


@router.post("/users/{identity}/enable")
async def enable(
    identity: str,
    principal: Principal = Depends(require("ad.enable_disable")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.user.enable",
        identity,
        "POST",
        f"/ad/users/{seg(identity)}/enable",
    )


@router.post("/users/{identity}/disable")
async def disable(
    identity: str,
    principal: Principal = Depends(require("ad.enable_disable")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.user.disable",
        identity,
        "POST",
        f"/ad/users/{seg(identity)}/disable",
    )


@router.post("/users/{identity}/reset-password")
async def reset_password(
    identity: str,
    body: PasswordBody,
    principal: Principal = Depends(require("ad.password")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.user.reset_password",
        identity,
        "POST",
        f"/ad/users/{seg(identity)}/reset-password",
        payload=body.model_dump(),
        details={"must_change": body.must_change},
    )


@router.post("/users/{identity}/move")
async def move_user(
    identity: str,
    body: MoveBody,
    principal: Principal = Depends(require("ad.update")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.user.move",
        identity,
        "POST",
        f"/ad/users/{seg(identity)}/move",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.get("/users/{identity}/groups")
async def user_groups(identity: str, _: Principal = Depends(require("group.read"))):
    return await worker.request("GET", f"/ad/users/{seg(identity)}/groups")


@router.get("/groups")
async def groups(
    q: str = Query(default="", max_length=80), _: Principal = Depends(require("group.read"))
):
    return await worker.request("GET", "/ad/groups", params={"q": q})


@router.post("/groups")
async def create_group(
    body: GroupCreate,
    principal: Principal = Depends(require("group.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.group.create",
        body.name,
        "POST",
        "/ad/groups",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.delete("/groups/{name}")
async def delete_group(
    name: str, principal: Principal = Depends(require("group.write")), db: Session = Depends(get_db)
):
    return await _audited(
        db,
        principal,
        "ad.group.delete",
        name,
        "DELETE",
        f"/ad/groups/{seg(name)}",
    )


@router.get("/groups/{name}/members")
async def group_members(name: str, _: Principal = Depends(require("group.read"))):
    return await worker.request("GET", f"/ad/groups/{seg(name)}/members")


@router.post("/groups/{name}/members")
async def add_group_member(
    name: str,
    body: MemberBody,
    principal: Principal = Depends(require("group.membership")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.group.member.add",
        name,
        "POST",
        f"/ad/groups/{seg(name)}/members",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.delete("/groups/{name}/members/{member}")
async def remove_group_member(
    name: str,
    member: str,
    principal: Principal = Depends(require("group.membership")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.group.member.remove",
        name,
        "DELETE",
        f"/ad/groups/{seg(name)}/members/{seg(member)}",
        details={"member": member},
    )


@router.get("/computers")
async def computers(
    q: str = Query(default="", max_length=80), _: Principal = Depends(require("computer.read"))
):
    return await worker.request("GET", "/ad/computers", params={"q": q})


@router.post("/computers/{name}/move")
async def move_computer(
    name: str,
    body: MoveBody,
    principal: Principal = Depends(require("computer.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.computer.move",
        name,
        "POST",
        f"/ad/computers/{seg(name)}/move",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/computers/{name}/{action}")
async def computer_action(
    name: str,
    action: Literal["enable", "disable", "reset"],
    principal: Principal = Depends(require("computer.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        f"ad.computer.{action}",
        name,
        "POST",
        f"/ad/computers/{seg(name)}/{action}",
    )


@router.delete("/computers/{name}")
async def delete_computer(
    name: str,
    principal: Principal = Depends(require("computer.delete")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.computer.delete",
        name,
        "DELETE",
        f"/ad/computers/{seg(name)}",
    )


@router.get("/ous")
async def ous(_: Principal = Depends(require("ou.read"))):
    return await worker.request("GET", "/ad/ous")


@router.post("/ous")
async def create_ou(
    body: OUCreate,
    principal: Principal = Depends(require("ou.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.ou.create",
        body.name,
        "POST",
        "/ad/ous",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/ous/delete")
async def delete_ou(
    body: OUDelete,
    principal: Principal = Depends(require("ou.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.ou.delete",
        body.dn,
        "POST",
        "/ad/ous/delete",
        payload=body.model_dump(),
        details={"recursive": body.recursive},
    )


@router.get("/deleted")
async def deleted_objects(_: Principal = Depends(require("ad.read"))):
    return await worker.request("GET", "/ad/deleted")


@router.post("/deleted/restore")
async def restore_object(
    body: RestoreBody,
    principal: Principal = Depends(require("ad.update")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "ad.object.restore",
        body.object_guid,
        "POST",
        "/ad/deleted/restore",
        payload=body.model_dump(),
        details={"target_path": body.target_path},
    )
