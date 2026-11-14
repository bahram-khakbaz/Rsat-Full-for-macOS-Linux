"""Request bodies. Limits mirror the control plane's API models."""

import re
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, StrictBool, model_validator

DnsRecordType = Literal["A", "AAAA", "CNAME", "PTR", "NS", "MX", "SRV", "TXT"]
_ZONE = r"^[A-Za-z0-9_.-]{1,253}$"
# "@" is the zone apex; one leading "*" label is a wildcard owner.
_OWNER = r"^(?:@|\*|(?:\*\.)?[A-Za-z0-9_.-]{1,253})$"
_WORKSTATIONS = re.compile(r"[A-Za-z0-9_.-]+(?:,[A-Za-z0-9_.-]+)*")


class PasswordBody(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)
    must_change: bool = True


class UserCreate(BaseModel):
    sam_account_name: str = Field(min_length=1, max_length=64)
    given_name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    email: str = Field(default="", max_length=256)
    department: str = Field(default="", max_length=256)
    title: str = Field(default="", max_length=256)
    company: str = Field(default="", max_length=256)
    manager: str = Field(default="", max_length=1024)
    ou: str = Field(min_length=3, max_length=1024)
    password: str = Field(min_length=8, max_length=256)
    enabled: bool = True
    must_change: bool = True


class UserPatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=256)
    department: str | None = Field(default=None, max_length=256)
    title: str | None = Field(default=None, max_length=256)
    company: str | None = Field(default=None, max_length=256)
    manager: str | None = Field(default=None, max_length=1024)
    mobile: str | None = Field(default=None, max_length=64)


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
        if self.logon_workstations and not _WORKSTATIONS.fullmatch(self.logon_workstations):
            raise ValueError("Use comma-separated workstation names")
        return self


class MoveBody(BaseModel):
    target_ou: str = Field(min_length=3, max_length=1024)


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scope: Literal["DomainLocal", "Global", "Universal"] = "Global"
    category: Literal["Security", "Distribution"] = "Security"
    path: str = Field(min_length=3, max_length=1024)
    description: str = Field(default="", max_length=1024)


class MemberBody(BaseModel):
    member: str = Field(min_length=1, max_length=512)


class OUCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    path: str = Field(min_length=3, max_length=1024)
    protected: bool = True


class OUDelete(BaseModel):
    dn: str = Field(min_length=3, max_length=1024)
    recursive: bool = False


class RestoreBody(BaseModel):
    object_guid: str = Field(min_length=36, max_length=36)
    target_path: str = Field(default="", max_length=1024)


class ZoneCreate(BaseModel):
    name: str = Field(pattern=_ZONE)
    replication_scope: Literal["Domain", "Forest", "Legacy"] = "Domain"
    dynamic_update: Literal["Secure", "NonsecureAndSecure", "None"] = "Secure"


class ZoneDelete(BaseModel):
    name: str = Field(pattern=_ZONE)


class DnsRecordBody(BaseModel):
    zone: str = Field(pattern=_ZONE)
    name: str = Field(pattern=_OWNER)
    type: DnsRecordType
    value: str = Field(min_length=1, max_length=2048)
    ttl: int = Field(default=3600, ge=60, le=86400)


class DnsUpdateBody(DnsRecordBody):
    old_value: str = Field(min_length=1, max_length=2048)
    old_ttl: int = Field(default=3600, ge=0, le=2147483647)


class DnsDeleteBody(BaseModel):
    zone: str = Field(pattern=_ZONE)
    name: str = Field(pattern=_OWNER)
    type: DnsRecordType
    value: str = Field(default="", max_length=2048)


class ScopeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    start_range: str = Field(max_length=64)
    end_range: str = Field(max_length=64)
    subnet_mask: str = Field(max_length=64)
    lease_days: int = Field(default=8, ge=1, le=365)
    state: Literal["Active", "Inactive"] = "Active"
    description: str = Field(default="", max_length=1024)


class ScopeDelete(BaseModel):
    scope_id: str = Field(max_length=64)


class ScopeState(BaseModel):
    scope_id: str = Field(max_length=64)
    state: Literal["Active", "Inactive"]


class ReservationBody(BaseModel):
    scope_id: str = Field(max_length=64)
    ip_address: str = Field(max_length=64)
    client_id: str = Field(pattern=r"^[A-Fa-f0-9:-]{11,40}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=250)


class ReservationDelete(BaseModel):
    scope_id: str = Field(max_length=64)
    ip_address: str = Field(max_length=64)


class GpoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    comment: str = Field(default="", max_length=500)


class GpoLink(BaseModel):
    target: str = Field(min_length=3, max_length=1024)
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
