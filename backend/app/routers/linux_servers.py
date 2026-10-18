"""Per-operator Linux inventory using the shared verified SSH terminal."""
import secrets

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..auth import Principal, require
from ..audit import write_audit
from ..db import SshLinuxServer, get_db
from ..secret_store import store_credential
from . import ssh

router = APIRouter(prefix="/api/ssh/linux-servers", tags=["linux-servers"])


def owned(db, identity, principal):
    return ssh.owned(db, identity, principal, SshLinuxServer)


@router.get("")
def servers(p: Principal = Depends(require("ssh.read")), db: Session = Depends(get_db)):
    return [ssh.public(row) for row in db.query(SshLinuxServer).filter_by(
        owner=p.username).order_by(SshLinuxServer.id).all()]


@router.post("")
def create(body: ssh.SwitchBody, p: Principal = Depends(require("ssh.write")),
           db: Session = Depends(get_db)):
    row = SshLinuxServer(owner=p.username,
        **body.model_dump(exclude={"password", "vault_key"}),
        password=store_credential(body.password,body.vault_key,p.username), fingerprint="")
    db.add(row); db.commit(); db.refresh(row)
    write_audit(db, p, "ssh.linux.create", row.host)
    return ssh.public(row)


@router.put("/{identity}")
def update(identity: int, body: ssh.SwitchBody,
           p: Principal = Depends(require("ssh.write")), db: Session = Depends(get_db)):
    row = owned(db, identity, p)
    changed = (row.host, row.port) != (body.host, body.port)
    if changed and not (body.password or body.vault_key):
        raise HTTPException(422, "Changing the host requires entering its password again")
    if changed:
        row.fingerprint = ""
    for key, value in body.model_dump(exclude={"password", "vault_key"}).items():
        setattr(row, key, value)
    row.password = store_credential(body.password,body.vault_key,p.username,row.password)
    db.commit()
    write_audit(db, p, "ssh.linux.update", row.host)
    return ssh.public(row)


@router.delete("/{identity}")
def delete(identity: int, p: Principal = Depends(require("ssh.write")),
           db: Session = Depends(get_db)):
    row = owned(db, identity, p); host = row.host
    db.delete(row); db.commit()
    write_audit(db, p, "ssh.linux.delete", host)
    return {"ok": True}


@router.post("/{identity}/inspect")
async def inspect_key(identity: int, p: Principal = Depends(require("ssh.connect")),
                      db: Session = Depends(get_db)):
    row = owned(db, identity, p)
    return await run_in_threadpool(ssh.inspect, row.host, row.port)


@router.post("/{identity}/trust")
async def trust(identity: int, body: ssh.TrustBody,
                p: Principal = Depends(require("ssh.write")), db: Session = Depends(get_db)):
    row = owned(db, identity, p)
    observed = await run_in_threadpool(ssh.inspect, row.host, row.port)
    if not secrets.compare_digest(observed["fingerprint"], body.fingerprint):
        raise HTTPException(409, "Host key changed. Inspect and verify again.")
    row.fingerprint = body.fingerprint; db.commit()
    write_audit(db, p, "ssh.linux.host_key.approve", row.host, details=observed)
    return ssh.public(row)


@router.post("/{identity}/ticket")
def ticket(identity: int, p: Principal = Depends(require("ssh.connect")),
           db: Session = Depends(get_db)):
    return ssh.issue_ticket(identity, p, owned(db, identity, p), scope="linux")


@router.websocket("/{identity}/terminal")
async def terminal(ws: WebSocket, identity: int):
    await ssh.terminal_session(ws, identity, SshLinuxServer, scope="linux")
