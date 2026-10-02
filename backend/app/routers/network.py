from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..auth import Principal, require
from ..db import get_db
from ..audit import write_audit
from ..worker_client import worker

router = APIRouter(prefix="/api", tags=["network"])

class DnsRecordBody(BaseModel):
    zone: str
    name: str
    type: str = "A"
    value: str
    ttl: int = 3600

class ReservationBody(BaseModel):
    scope_id: str
    ip_address: str
    client_id: str
    name: str
    description: str = ""

@router.get("/dns/records")
async def dns_records(_: Principal = Depends(require("dns.read"))):
    return await worker.request("GET", "/dns/records")

@router.post("/dns/records")
async def dns_create(body: DnsRecordBody, principal: Principal = Depends(require("dns.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/dns/records", payload=body.model_dump())
    write_audit(db, principal, "dns.record.create", f"{body.name}.{body.zone}", details=body.model_dump())
    return result

@router.get("/dhcp/scopes")
async def dhcp_scopes(_: Principal = Depends(require("dhcp.read"))):
    return await worker.request("GET", "/dhcp/scopes")

@router.post("/dhcp/reservations")
async def dhcp_reservation(body: ReservationBody, principal: Principal = Depends(require("dhcp.write")), db: Session = Depends(get_db)):
    result = await worker.request("POST", "/dhcp/reservations", payload=body.model_dump())
    write_audit(db, principal, "dhcp.reservation.create", body.ip_address, details=body.model_dump())
    return result
