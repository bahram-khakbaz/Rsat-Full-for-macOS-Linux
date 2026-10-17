"""Manual IPv4 allocation inventory; never probes or changes the network."""
import ipaddress
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..auth import Principal, require
from ..audit import write_audit
from ..db import IpamVlan, get_db

router = APIRouter(prefix="/api/ipam/vlans", tags=["ipam"])
State = Literal["free", "used", "reserved", "unknown"]


def network(value):
    try:
        net = ipaddress.IPv4Network(value, strict=False)
        if not 4 <= net.num_addresses <= 4096:
            raise ValueError()
        return net
    except ValueError:
        raise HTTPException(422, "Use an IPv4 subnet from /20 through /30")


def usable(net, value):
    try:
        ip = ipaddress.IPv4Address(value)
    except ValueError:
        raise HTTPException(422, "Invalid IPv4 address")
    if ip not in net or ip in (net.network_address, net.broadcast_address):
        raise HTTPException(422, "Address must be a usable host in this subnet")
    return str(ip)


class VlanBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    cidr: str = Field(max_length=32)
    default_status: State = "unknown"
    states: dict[str, State] = Field(default_factory=dict, max_length=4094)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Enter a VLAN name")
        return value.strip()


class AddressBody(BaseModel):
    status: State
    revision: int = Field(ge=1)


def owned(db, identity, principal):
    row = db.query(IpamVlan).filter_by(id=identity, owner=principal.username).first()
    if row is None:
        raise HTTPException(404, "VLAN not found")
    return row


def public(row):
    net = network(row.cidr)
    states = json.loads(row.states)
    addresses = [{"ip": str(ip), "status": states.get(str(ip), row.default_status)} for ip in net.hosts()]
    counts = {state: sum(a["status"] == state for a in addresses) for state in ("free", "used", "reserved", "unknown")}
    return {"id": row.id, "name": row.name, "cidr": row.cidr, "revision": row.revision,
            "network": str(net.network_address), "broadcast": str(net.broadcast_address),
            "total": len(addresses), "counts": counts, "addresses": addresses}


@router.get("")
def vlans(p: Principal = Depends(require("ipam.read")), db: Session = Depends(get_db)):
    return [public(row) for row in db.query(IpamVlan).filter_by(owner=p.username).order_by(IpamVlan.id).all()]


@router.post("")
def create(body: VlanBody, p: Principal = Depends(require("ipam.write")), db: Session = Depends(get_db)):
    net = network(body.cidr)
    for existing in db.query(IpamVlan).filter_by(owner=p.username):
        if net.overlaps(network(existing.cidr)):
            raise HTTPException(409, "This subnet overlaps an existing VLAN in your inventory")
    states = {usable(net, ip): state for ip, state in body.states.items()}
    row = IpamVlan(owner=p.username, name=body.name, cidr=str(net),
                   default_status=body.default_status, states=json.dumps(states))
    db.add(row)
    db.commit()
    db.refresh(row)
    write_audit(db, p, "ipam.vlan.create", row.cidr)
    return public(row)


@router.patch("/{identity}/addresses/{address}")
def set_address(identity: int, address: str, body: AddressBody,
                p: Principal = Depends(require("ipam.write")), db: Session = Depends(get_db)):
    row = owned(db, identity, p)
    address = usable(network(row.cidr), address)
    states = json.loads(row.states)
    previous = states.get(address, row.default_status)
    states[address] = body.status
    result = db.execute(update(IpamVlan).where(IpamVlan.id == identity,
        IpamVlan.owner == p.username, IpamVlan.revision == body.revision).values(
            states=json.dumps(states), revision=body.revision + 1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "VLAN changed in another window. Refresh and try again")
    db.commit()
    write_audit(db, p, "ipam.address.update", address, details={"before": previous, "after": body.status})
    db.refresh(row)
    return public(row)
