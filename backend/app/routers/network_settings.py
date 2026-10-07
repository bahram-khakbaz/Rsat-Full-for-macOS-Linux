import json
import re
from typing import Literal
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy.orm import Session
from ..auth import Principal,require
from ..audit import write_audit
from ..db import get_db,SystemSetting
from ..native_network import configuration_network,reset_auth_failure

router=APIRouter(prefix='/api/network-connection',tags=['network settings'])
class ServiceBody(BaseModel):
    dns_host:str=Field(default='',max_length=255)
    dhcp_host:str=Field(default='',max_length=255)
    dns_mode:Literal['Direct','LDAP','WinRM']='Direct'
    dhcp_mode:Literal['RPC','WinRM']='RPC'
    port:int=Field(default=5985,ge=1,le=65535)
    @field_validator('dns_host','dhcp_host')
    @classmethod
    def valid_host(cls,value):
        value=value.strip().lower()
        if value and not re.fullmatch(r'[a-z0-9][a-z0-9.-]*',value):raise ValueError('Use the server FQDN, not a URL or IP')
        return value
@router.get('')
def read(p:Principal=Depends(require('domain.read'))):
    cfg,network=configuration_network()
    return {**network,'domain':cfg.get('domain',''),'username':cfg.get('username',''),'authentication':'Kerberos / encrypted service RPC (WinRM optional)','password_configured':bool(cfg.get('password'))}
@router.put('')
def save(body:ServiceBody,p:Principal=Depends(require('settings.write')),db:Session=Depends(get_db)):
    cfg,_=configuration_network()
    for host in (body.dns_host,body.dhcp_host):
        if host and not host.endswith('.'+cfg.get('domain','').lower()):raise HTTPException(422,'Service host must belong to the configured AD domain')
    row=db.query(SystemSetting).filter_by(key='native_network').first()
    if row:row.value=json.dumps(body.model_dump())
    else:db.add(SystemSetting(key='native_network',value=json.dumps(body.model_dump())))
    db.commit();reset_auth_failure();write_audit(db,p,'network.connection.save',details=body.model_dump())
    return {'ok':True}

@router.get('/dhcp-servers')
async def discover(p:Principal=Depends(require('dhcp.read'))):
    from ..native_dns import dhcp_servers
    return await run_in_threadpool(dhcp_servers)

@router.post('/test-dns')
async def test_dns(p:Principal=Depends(require('dns.read'))):
    from ..dns_rpc import request
    cfg,network=configuration_network()
    return await run_in_threadpool(request,cfg,network['dns_host'],{'zone':cfg['domain']},probe=True)
