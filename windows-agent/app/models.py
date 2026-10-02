from typing import Literal
from pydantic import BaseModel, Field

class PasswordBody(BaseModel):
    new_password: str = Field(min_length=12, max_length=256)
    must_change: bool = True

class UserCreate(BaseModel):
    sam_account_name: str = Field(min_length=1, max_length=64)
    given_name: str
    surname: str
    display_name: str
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
    target_ou: str

class GroupCreate(BaseModel):
    name: str
    scope: Literal["DomainLocal","Global","Universal"] = "Global"
    category: Literal["Security","Distribution"] = "Security"
    path: str
    description: str = ""

class MemberBody(BaseModel):
    member: str

class OUCreate(BaseModel):
    name: str
    path: str
    protected: bool = True

class OUDelete(BaseModel):
    dn: str
    recursive: bool = False

class RestoreBody(BaseModel):
    object_guid: str = Field(min_length=36, max_length=36)
    target_path: str = ""

class ZoneCreate(BaseModel):
    name: str
    replication_scope: Literal["Domain","Forest","Legacy"] = "Domain"
    dynamic_update: Literal["Secure","NonsecureAndSecure","None"] = "Secure"

class ZoneDelete(BaseModel):
    name: str

class DnsRecordBody(BaseModel):
    zone: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(pattern=r"^[A-Za-z0-9_.@-]+$")
    type: Literal["A","AAAA","CNAME","PTR"]
    value: str
    ttl: int = Field(default=3600, ge=60, le=86400)

class DnsDeleteBody(BaseModel):
    zone: str
    name: str
    type: Literal["A","AAAA","CNAME","PTR"]
    value: str = ""

class ScopeCreate(BaseModel):
    name: str
    start_range: str
    end_range: str
    subnet_mask: str
    lease_days: int = Field(default=8, ge=1, le=365)
    state: Literal["Active","Inactive"] = "Active"
    description: str = ""

class ScopeDelete(BaseModel):
    scope_id: str

class ScopeState(BaseModel):
    scope_id: str
    state: Literal["Active","Inactive"]

class ReservationBody(BaseModel):
    scope_id: str
    ip_address: str
    client_id: str = Field(pattern=r"^[A-Fa-f0-9:-]{11,40}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=250)

class ReservationDelete(BaseModel):
    scope_id: str
    ip_address: str

class GpoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    comment: str = Field(default="", max_length=500)

class GpoLink(BaseModel):
    target: str
    enforced: bool = False
    enabled: bool = True
    order: int | None = None

class GpoStatus(BaseModel):
    status: Literal["AllSettingsEnabled","UserSettingsDisabled","ComputerSettingsDisabled","AllSettingsDisabled"]

class BackupBody(BaseModel):
    path: str = Field(min_length=3, max_length=1024)

class GpoPermission(BaseModel):
    trustee: str = Field(min_length=1, max_length=256)
    target_type: Literal["User","Group","Computer"] = "Group"
    permission: Literal["GpoRead","GpoApply","GpoEdit","GpoEditDeleteModifySecurity"] = "GpoRead"
    replace: bool = False
