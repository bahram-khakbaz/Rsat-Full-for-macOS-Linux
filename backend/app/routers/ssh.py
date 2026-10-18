"""Saved per-operator SSH switches and an authenticated interactive PTY."""
import asyncio
import base64
import hashlib
import json
import secrets
import socket
import time
from urllib.parse import urlparse
import paramiko
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from ..auth import Principal, require
from ..audit import write_audit
from ..db import SessionLocal, SshSwitch, get_db
from ..secret_store import encrypt_secret, decrypt_secret, store_credential
from ..vault_agent import metadata as credential_metadata

router = APIRouter(prefix='/api/ssh', tags=['ssh'])
_tickets = {}

class SwitchBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(default="", max_length=255)
    password: str = Field(default='', max_length=4096)
    vault_key: str | None = Field(default=None, max_length=80)
    @field_validator('host')
    @classmethod
    def host_only(cls, value):
        import re
        value=value.strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9.:-]*',value):
            raise ValueError('Enter a hostname or IP, without a URL or path')
        return value

class TrustBody(BaseModel):
    fingerprint: str = Field(min_length=20, max_length=100)

def public(row):
    return {k:getattr(row,k) for k in ('id','name','host','port','username','fingerprint')} | {'password_configured':bool(row.password)} | credential_metadata(row.password)

def owned(db, identity, principal, model=SshSwitch):
    row=db.query(model).filter_by(id=identity,owner=principal.username).first()
    if not row: raise HTTPException(404,'SSH device not found')
    return row

def fingerprint(key):
    return 'SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')

def transport(host,port):
    sock=socket.create_connection((host,port),timeout=8)
    t=paramiko.Transport(sock)
    t.banner_timeout=8
    t.auth_timeout=12
    try:
        t.start_client(timeout=8)
        return t
    except Exception:
        t.close()
        raise

def inspect(host,port):
    t=None
    try:
        t=transport(host,port)
        key=t.get_remote_server_key()
        return {'fingerprint':fingerprint(key),'algorithm':key.get_name(),'host':host,'port':port}
    except (OSError,paramiko.SSHException) as exc:
        raise HTTPException(502,'SSH handshake failed. Check VPN, hostname and SSH port.') from exc
    finally:
        if t:t.close()

@router.get('/switches')
def switches(p:Principal=Depends(require('ssh.read')),db:Session=Depends(get_db)):
    return [public(x) for x in db.query(SshSwitch).filter_by(owner=p.username).order_by(SshSwitch.id).all()]

@router.post('/switches')
def create(body:SwitchBody,p:Principal=Depends(require('ssh.write')),db:Session=Depends(get_db)):
    row=SshSwitch(owner=p.username,**body.model_dump(exclude={'password','vault_key'}),password=store_credential(body.password,body.vault_key,p.username),fingerprint='')
    db.add(row);db.commit();db.refresh(row)
    write_audit(db,p,'ssh.switch.create',row.host)
    return public(row)

@router.put('/switches/{identity}')
def update(identity:int,body:SwitchBody,p:Principal=Depends(require('ssh.write')),db:Session=Depends(get_db)):
    row=owned(db,identity,p)
    destination_changed=(row.host,row.port)!=(body.host,body.port)
    if destination_changed and not (body.password or body.vault_key):
        raise HTTPException(422,'Changing the host requires entering its password again')
    if destination_changed:row.fingerprint=''
    for k,v in body.model_dump(exclude={'password','vault_key'}).items():setattr(row,k,v)
    row.password=store_credential(body.password,body.vault_key,p.username,row.password)
    db.commit();write_audit(db,p,'ssh.switch.update',row.host)
    return public(row)

@router.delete('/switches/{identity}')
def delete(identity:int,p:Principal=Depends(require('ssh.write')),db:Session=Depends(get_db)):
    row=owned(db,identity,p);host=row.host;db.delete(row);db.commit()
    write_audit(db,p,'ssh.switch.delete',host)
    return {'ok':True}

@router.post('/switches/{identity}/inspect')
async def inspect_key(identity:int,p:Principal=Depends(require('ssh.connect')),db:Session=Depends(get_db)):
    row=owned(db,identity,p)
    return await run_in_threadpool(inspect,row.host,row.port)

@router.post('/switches/{identity}/trust')
async def trust(identity:int,body:TrustBody,p:Principal=Depends(require('ssh.write')),db:Session=Depends(get_db)):
    row=owned(db,identity,p)
    observed=await run_in_threadpool(inspect,row.host,row.port)
    if not secrets.compare_digest(observed['fingerprint'],body.fingerprint):
        raise HTTPException(409,'Host key changed. Inspect and verify again.')
    row.fingerprint=body.fingerprint;db.commit()
    write_audit(db,p,'ssh.host_key.approve',row.host,details=observed)
    return public(row)

@router.post('/switches/{identity}/ticket')
def ticket(identity:int,p:Principal=Depends(require('ssh.connect')),db:Session=Depends(get_db)):
    row=owned(db,identity,p)
    return issue_ticket(identity,p,row)

def issue_ticket(identity,p,row,scope="switch"):
    if not row.fingerprint:raise HTTPException(409,'Inspect and approve the SSH device host key first')
    if not row.username.strip():raise HTTPException(409,'Save the SSH device username first')
    if not row.password:raise HTTPException(409,'Save the SSH device password or Vault Agent key first')
    now=time.monotonic()
    for key in list(_tickets):
        if _tickets[key]['expires']<now: _tickets.pop(key,None)
    if len(_tickets)>500:raise HTTPException(429,'Too many pending connections')
    key=secrets.token_urlsafe(32)
    _tickets[key]={'identity':identity,'principal':p,'expires':now+30,'scope':scope}
    return {'ticket':key}

def consume_ticket(key,identity,scope="switch"):
    entry=_tickets.pop(key,None)
    if not entry or entry['identity']!=identity or entry.get('scope','switch')!=scope or entry['expires']<time.monotonic():
        raise HTTPException(401,'Connection ticket expired. Click Connect again.')
    return entry['principal']

def open_shell(row):
    t=transport(row['host'],row['port'])
    try:
        if not secrets.compare_digest(fingerprint(t.get_remote_server_key()),row['fingerprint']):
            raise HTTPException(409,'SSH host key changed. No password was sent. Verify the new key first.')
        password=decrypt_secret(row['password'])
        if not password:raise HTTPException(409,'The saved SSH credential is unavailable')
        try:
            t.auth_password(row['username'],password,fallback=False)
        except paramiko.BadAuthenticationType as exc:
            if 'keyboard-interactive' not in exc.allowed_types:raise
            def answer(title,instructions,prompts):
                if len(prompts)!=1 or prompts[0][1] or 'password' not in prompts[0][0].lower() or any(word in prompts[0][0].lower() for word in ('new','otp','token','code')):
                    raise HTTPException(409,'This SSH host requires an additional authentication challenge. Saved-password login cannot answer it.')
                return [password]
            t.auth_interactive(row['username'],answer)
        t.set_keepalive(20)
        channel=t.open_session(timeout=10)
        channel.get_pty(term='xterm',width=100,height=30)
        channel.invoke_shell()
        channel.settimeout(1)
        return t,channel
    except Exception:
        t.close();raise

@router.websocket('/switches/{identity}/terminal')
async def terminal(ws:WebSocket,identity:int):
    await terminal_session(ws,identity)

async def terminal_session(ws:WebSocket,identity:int,model=SshSwitch,scope="switch"):
    # Ticket travels in the first frame, never in URLs or HTTP access logs.
    origin=ws.headers.get('origin')
    if origin and urlparse(origin).netloc!=ws.headers.get('host'):
        await ws.close(code=1008);return
    await ws.accept()
    t=channel=None
    tasks=[];p=None;host=''
    try:
        hello=await asyncio.wait_for(ws.receive_json(),timeout=10)
        p=consume_ticket(hello.get('ticket',''),identity,scope)
        with SessionLocal() as db:
            r=owned(db,identity,p,model)
            row={k:getattr(r,k) for k in ('host','port','username','password','fingerprint')}
            host=r.host
        t,channel=await run_in_threadpool(open_shell,row)
        with SessionLocal() as db:write_audit(db,p,'ssh.connect',host)
        await ws.send_json({'type':'ready'})
        async def output():
            while not channel.closed:
                try:data=await asyncio.to_thread(channel.recv,32768)
                except socket.timeout:continue
                if not data:return
                await ws.send_json({'type':'output','data':base64.b64encode(data).decode()})
        async def input_stream():
            while True:
                msg=await ws.receive_json()
                if msg.get('type')=='input':
                    data=msg.get('data','')
                    if not isinstance(data,str) or len(data)>16384:raise HTTPException(422,'Terminal input too large')
                    await asyncio.to_thread(channel.sendall,data.encode())
                elif msg.get('type')=='resize':
                    width=max(20,min(300,int(msg.get('cols',100))))
                    height=max(5,min(100,int(msg.get('rows',30))))
                    await asyncio.to_thread(channel.resize_pty,width=width,height=height)
                elif msg.get('type')=='disconnect':return
        tasks=[asyncio.create_task(output()),asyncio.create_task(input_stream())]
        await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        for task in tasks:
            if task.done() and not task.cancelled() and task.exception():raise task.exception()
    except WebSocketDisconnect:pass
    except Exception as exc:
        message=exc.detail if isinstance(exc,HTTPException) else 'SSH authentication or session failed. Check the account, VPN and device SSH settings.'
        try:await ws.send_json({'type':'error','message':message})
        except Exception:pass
        if p:
            with SessionLocal() as db:write_audit(db,p,'ssh.connect',host,status='failed')
    finally:
        if channel:channel.close()
        if t:t.close()
        for task in tasks:task.cancel()
        # The peer may cancel the websocket task at its next await. Record
        # disconnect after closing the native handles, before yielding again.
        if p and t:
            with SessionLocal() as db:write_audit(db,p,'ssh.disconnect',host)
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        try:await ws.close()
        except Exception:pass
