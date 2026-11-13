from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import audited, write_audit
from ..auth import Principal, require
from ..db import get_db
from ..worker_client import worker

router = APIRouter(prefix="/api", tags=["network"])


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


class DnsRecordBody(BaseModel):
    zone: str
    name: str
    type: Literal["A", "AAAA", "CNAME", "PTR", "NS", "MX", "SRV", "TXT"]
    value: str
    ttl: int = Field(default=3600, ge=60, le=86400)


class DnsUpdateBody(DnsRecordBody):
    old_value: str
    old_ttl: int = Field(default=3600, ge=0, le=2147483647)


class DnsDeleteBody(BaseModel):
    zone: str
    name: str
    type: Literal["A", "AAAA", "CNAME", "PTR", "NS", "MX", "SRV", "TXT"]
    value: str = ""


class ZoneCreate(BaseModel):
    name: str
    replication_scope: Literal["Domain", "Forest", "Legacy"] = "Domain"
    dynamic_update: Literal["Secure", "NonsecureAndSecure", "None"] = "Secure"


class ZoneDelete(BaseModel):
    name: str


class ScopeCreate(BaseModel):
    name: str
    start_range: str
    end_range: str
    subnet_mask: str
    lease_days: int = Field(default=8, ge=1, le=365)
    state: Literal["Active", "Inactive"] = "Active"
    description: str = ""


class ScopeDelete(BaseModel):
    scope_id: str


class ScopeState(BaseModel):
    scope_id: str
    state: Literal["Active", "Inactive"]


class ReservationBody(BaseModel):
    scope_id: str
    ip_address: str
    client_id: str
    name: str
    description: str = ""


class ReservationDelete(BaseModel):
    scope_id: str
    ip_address: str


@router.get("/dns/zones")
async def dns_zones(_: Principal = Depends(require("dns.read"))):
    return await worker.request("GET", "/dns/zones")


@router.post("/dns/zones")
async def dns_zone_create(
    body: ZoneCreate,
    principal: Principal = Depends(require("dns.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dns.zone.create",
        body.name,
        "POST",
        "/dns/zones",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/dns/zones/delete")
async def dns_zone_delete(
    body: ZoneDelete,
    principal: Principal = Depends(require("dns.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dns.zone.delete",
        body.name,
        "POST",
        "/dns/zones/delete",
        payload=body.model_dump(),
    )


@router.get("/dns/records")
async def dns_records(zone: str = Query(default=""), _: Principal = Depends(require("dns.read"))):
    return await worker.request("GET", "/dns/records", params={"zone": zone})


@router.post("/dns/records")
async def dns_create(
    body: DnsRecordBody,
    principal: Principal = Depends(require("dns.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dns.record.create",
        f"{body.name}.{body.zone}",
        "POST",
        "/dns/records",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/dns/records/update")
async def dns_update(
    body: DnsUpdateBody,
    principal: Principal = Depends(require("dns.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dns.record.update",
        body.name,
        "POST",
        "/dns/records/update",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/dns/records/delete")
async def dns_delete(
    body: DnsDeleteBody,
    principal: Principal = Depends(require("dns.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dns.record.delete",
        f"{body.name}.{body.zone}",
        "POST",
        "/dns/records/delete",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.get("/dhcp/scopes")
async def dhcp_scopes(_: Principal = Depends(require("dhcp.read"))):
    return await worker.request("GET", "/dhcp/scopes")


@router.post("/dhcp/scopes")
async def dhcp_scope_create(
    body: ScopeCreate,
    principal: Principal = Depends(require("dhcp.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dhcp.scope.create",
        body.name,
        "POST",
        "/dhcp/scopes",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/dhcp/scopes/delete")
async def dhcp_scope_delete(
    body: ScopeDelete,
    principal: Principal = Depends(require("dhcp.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dhcp.scope.delete",
        body.scope_id,
        "POST",
        "/dhcp/scopes/delete",
        payload=body.model_dump(),
    )


@router.post("/dhcp/scopes/state")
async def dhcp_scope_state(
    body: ScopeState,
    principal: Principal = Depends(require("dhcp.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dhcp.scope.state",
        body.scope_id,
        "POST",
        "/dhcp/scopes/state",
        payload=body.model_dump(),
        details={"state": body.state},
    )


@router.get("/dhcp/leases")
async def dhcp_leases(
    scope_id: str = Query(default=""), _: Principal = Depends(require("dhcp.read"))
):
    return await worker.request("GET", "/dhcp/leases", params={"scope_id": scope_id})


@router.get("/dhcp/reservations")
async def dhcp_reservations(
    scope_id: str = Query(default=""), _: Principal = Depends(require("dhcp.read"))
):
    return await worker.request("GET", "/dhcp/reservations", params={"scope_id": scope_id})


@router.post("/dhcp/reservations")
async def dhcp_reservation(
    body: ReservationBody,
    principal: Principal = Depends(require("dhcp.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dhcp.reservation.create",
        body.ip_address,
        "POST",
        "/dhcp/reservations",
        payload=body.model_dump(),
        details=body.model_dump(),
    )


@router.post("/dhcp/reservations/delete")
async def dhcp_reservation_delete(
    body: ReservationDelete,
    principal: Principal = Depends(require("dhcp.write")),
    db: Session = Depends(get_db),
):
    return await _audited(
        db,
        principal,
        "dhcp.reservation.delete",
        body.ip_address,
        "POST",
        "/dhcp/reservations/delete",
        payload=body.model_dump(),
        details=body.model_dump(),
    )
