from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..auth import Principal, require
from ..db import get_db
from ..audit import write_audit
from ..worker_client import worker

router = APIRouter(prefix="/api/ad", tags=["active-directory"])

class PasswordBody(BaseModel):
    new_password: str = Field(min_length=12, max_length=256)
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
    password: str = Field(min_length=12, max_length=256)
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

@router.get("/users")
async def users(q: str = Query(default="", max_length=80), _: Principal = Depends(require("ad.read"))):
    return await worker.request("GET", "/ad/users", params={"q": q})

@router.post("/users")
async def create_user(body: UserCreate, principal: Principal = Depends(require("ad.create")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/ad/users", payload=body.model_dump())
    write_audit(db, principal, "ad.user.create", body.sam_account_name, details=body.model_dump(exclude={"password"}))
    return result

@router.get("/users/{identity}")
async def user(identity: str, _: Principal = Depends(require("ad.read"))):
    return await worker.request("GET", f"/ad/users/{identity}")

@router.patch("/users/{identity}")
async def update_user(identity: str, body: UserPatch, principal: Principal = Depends(require("ad.update")), db: Session = Depends(get_db)):
    payload = body.model_dump(exclude_none=True)
    result = await worker.request("PATCH", f"/ad/users/{identity}", payload=payload)
    write_audit(db, principal, "ad.user.update", identity, details=payload)
    return result

@router.delete("/users/{identity}")
async def delete_user(identity: str, principal: Principal = Depends(require("ad.delete")), db: Session = Depends(get_db)):
    result = await worker.request("DELETE", f"/ad/users/{identity}")
    write_audit(db, principal, "ad.user.delete", identity)
    return result

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

@router.post("/users/{identity}/move")
async def move_user(identity: str, body: MoveBody, principal: Principal = Depends(require("ad.update")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/ad/users/{identity}/move", payload=body.model_dump())
    write_audit(db, principal, "ad.user.move", identity, details=body.model_dump())
    return result

@router.get("/users/{identity}/groups")
async def user_groups(identity: str, _: Principal = Depends(require("group.read"))):
    return await worker.request("GET", f"/ad/users/{identity}/groups")

@router.get("/groups")
async def groups(_: Principal = Depends(require("group.read"))):
    return await worker.request("GET", "/ad/groups")

@router.post("/groups")
async def create_group(body: GroupCreate, principal: Principal = Depends(require("group.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/ad/groups", payload=body.model_dump())
    write_audit(db, principal, "ad.group.create", body.name, details=body.model_dump())
    return result

@router.delete("/groups/{name}")
async def delete_group(name: str, principal: Principal = Depends(require("group.write")), db: Session = Depends(get_db)):
    result = await worker.request("DELETE", f"/ad/groups/{name}")
    write_audit(db, principal, "ad.group.delete", name)
    return result

@router.get("/groups/{name}/members")
async def group_members(name: str, _: Principal = Depends(require("group.read"))):
    return await worker.request("GET", f"/ad/groups/{name}/members")

@router.post("/groups/{name}/members")
async def add_group_member(name: str, body: MemberBody, principal: Principal = Depends(require("group.membership")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/ad/groups/{name}/members", payload=body.model_dump())
    write_audit(db, principal, "ad.group.member.add", name, details=body.model_dump())
    return result

@router.delete("/groups/{name}/members/{member}")
async def remove_group_member(name: str, member: str, principal: Principal = Depends(require("group.membership")), db: Session = Depends(get_db)):
    result = await worker.request("DELETE", f"/ad/groups/{name}/members/{member}")
    write_audit(db, principal, "ad.group.member.remove", name, details={"member": member})
    return result

@router.get("/computers")
async def computers(q: str = Query(default="", max_length=80), _: Principal = Depends(require("computer.read"))):
    return await worker.request("GET", "/ad/computers", params={"q": q})

@router.post("/computers/{name}/{action}")
async def computer_action(name: str, action: Literal["enable","disable","reset"], principal: Principal = Depends(require("computer.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/ad/computers/{name}/{action}")
    write_audit(db, principal, f"ad.computer.{action}", name)
    return result

@router.post("/computers/{name}/move")
async def move_computer(name: str, body: MoveBody, principal: Principal = Depends(require("computer.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", f"/ad/computers/{name}/move", payload=body.model_dump())
    write_audit(db, principal, "ad.computer.move", name, details=body.model_dump())
    return result

@router.delete("/computers/{name}")
async def delete_computer(name: str, principal: Principal = Depends(require("computer.delete")), db: Session = Depends(get_db)):
    result = await worker.request("DELETE", f"/ad/computers/{name}")
    write_audit(db, principal, "ad.computer.delete", name)
    return result

@router.get("/ous")
async def ous(_: Principal = Depends(require("ou.read"))):
    return await worker.request("GET", "/ad/ous")

@router.post("/ous")
async def create_ou(body: OUCreate, principal: Principal = Depends(require("ou.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/ad/ous", payload=body.model_dump())
    write_audit(db, principal, "ad.ou.create", body.name, details=body.model_dump())
    return result

@router.post("/ous/delete")
async def delete_ou(body: OUDelete, principal: Principal = Depends(require("ou.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/ad/ous/delete", payload=body.model_dump())
    write_audit(db, principal, "ad.ou.delete", body.dn, details={"recursive": body.recursive})
    return result
