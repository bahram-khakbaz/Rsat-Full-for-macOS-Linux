from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..auth import Principal, require
from ..db import get_db
from ..audit import write_audit
from ..worker_client import worker

router = APIRouter(prefix="/api", tags=["network"])

class DnsRecordBody(BaseModel):
    zone: str
    name: str
    type: Literal["A","AAAA","CNAME","PTR"]
    value: str
    ttl: int = Field(default=3600, ge=60, le=86400)

class DnsDeleteBody(BaseModel):
    zone: str
    name: str
    type: Literal["A","AAAA","CNAME","PTR"]
    value: str = ""

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

@router.get("/dns/records")
async def dns_records(zone: str = Query(default=""), _: Principal = Depends(require("dns.read"))):
    return await worker.request("GET", "/dns/records", params={"zone": zone})

@router.post("/dns/records")
async def dns_create(body: DnsRecordBody, principal: Principal = Depends(require("dns.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/dns/records", payload=body.model_dump())
    write_audit(db, principal, "dns.record.create", f"{body.name}.{body.zone}", details=body.model_dump())
    return result

@router.post("/dns/records/delete")
async def dns_delete(body: DnsDeleteBody, principal: Principal = Depends(require("dns.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/dns/records/delete", payload=body.model_dump())
    write_audit(db, principal, "dns.record.delete", f"{body.name}.{body.zone}", details=body.model_dump())
    return result

@router.get("/dhcp/scopes")
async def dhcp_scopes(_: Principal = Depends(require("dhcp.read"))):
    return await worker.request("GET", "/dhcp/scopes")

@router.get("/dhcp/leases")
async def dhcp_leases(scope_id: str = Query(default=""), _: Principal = Depends(require("dhcp.read"))):
    return await worker.request("GET", "/dhcp/leases", params={"scope_id": scope_id})

@router.get("/dhcp/reservations")
async def dhcp_reservations(scope_id: str = Query(default=""), _: Principal = Depends(require("dhcp.read"))):
    return await worker.request("GET", "/dhcp/reservations", params={"scope_id": scope_id})

@router.post("/dhcp/reservations")
async def dhcp_reservation(body: ReservationBody, principal: Principal = Depends(require("dhcp.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/dhcp/reservations", payload=body.model_dump())
    write_audit(db, principal, "dhcp.reservation.create", body.ip_address, details=body.model_dump())
    return result

@router.post("/dhcp/reservations/delete")
async def dhcp_reservation_delete(body: ReservationDelete, principal: Principal = Depends(require("dhcp.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/dhcp/reservations/delete", payload=body.model_dump())
    write_audit(db, principal, "dhcp.reservation.delete", body.ip_address, details=body.model_dump())
    return result
