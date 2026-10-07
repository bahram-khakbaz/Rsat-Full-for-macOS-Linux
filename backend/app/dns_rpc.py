"""Validated direct DNS record management through the DNS service RPC API."""
import ipaddress
import json
import re
import shlex
import subprocess
from pathlib import Path
from fastapi import HTTPException
from .kerberos_cache import credential_cache


def dns_name(value,allow_wildcard=False):
    value=value.strip().rstrip('.').lower()
    if not value or len(value)>253:raise HTTPException(422,'Invalid DNS name')
    labels=value.split('.')
    for index,label in enumerate(labels):
        if allow_wildcard and index==0 and label=='*':continue
        if len(label)>63 or not re.fullmatch(r'[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?',label):raise HTTPException(422,'Invalid DNS label')
    return value


def parameters(host,body,delete=False,probe=False,update=False):
    host=dns_name(host);zone=dns_name(body['zone'])
    if probe:return {'host':host,'zone':zone,'operation':'probe'}
    name=body['name'].strip()
    if name!='@':
        name=dns_name(name,allow_wildcard=True)
        if name==zone:name='@'
        elif name.endswith('.'+zone):name=name[:-len(zone)-1]
    kind=body['type'];value=body['value'].strip()
    if kind not in ('A','AAAA','CNAME','PTR','NS','MX','SRV','TXT'):raise HTTPException(422,'Unsupported DNS record type')
    try:
        if kind in ('A','AAAA'):
            ip=ipaddress.ip_address(value)
            if ip.version!=(4 if kind=='A' else 6):raise ValueError()
            value=str(ip)
        elif kind in ('CNAME','PTR','NS'):value=dns_name(value)
        elif kind=='MX':
            priority,target=value.split()
            priority=int(priority)
            if not 0<=priority<=65535:raise ValueError()
            value=str(priority)+' '+dns_name(target)
        elif kind=='SRV':
            priority,weight,port,target=value.split()
            numbers=[int(x) for x in (priority,weight,port)]
            if any(not 0<=x<=65535 for x in numbers):raise ValueError()
            value=' '.join(str(x) for x in numbers)+' '+('.' if target=='.' else dns_name(target))
        else:
            segments=shlex.split(value)
            if not segments or any(len(x.encode('utf-8'))>255 for x in segments):raise ValueError()
            value=shlex.join(segments)
        ttl=int(body.get('ttl',3600))
        if not 60<=ttl<=86400:raise ValueError()
    except ValueError as exc:raise HTTPException(422,'Invalid DNS value, format or TTL') from exc
    if len(name)+len(zone)+1>253 and name!='@':raise HTTPException(422,'DNS name is too long')
    data={'host':host,'zone':zone,'name':name,'type':kind,'value':value,'ttl':ttl,'operation':'update' if update else 'delete' if delete else 'add'}
    if update:
        old=parameters(host,{**body,'value':body['old_value'],'ttl':3600})
        old_ttl=int(body.get('old_ttl',3600))
        if not 0<=old_ttl<=2147483647:raise HTTPException(422,'Invalid original TTL')
        data.update(old_value=old['value'],old_ttl=old_ttl)
    return data


def request(cfg,host,body,delete=False,probe=False,update=False):
    data=parameters(host,body,delete,probe,update)
    with credential_cache(cfg) as env:
        try:r=subprocess.run(['/usr/bin/python3',str(Path(__file__).with_name('samba_dns_rpc.py'))],input=json.dumps(data),text=True,capture_output=True,env=env,timeout=25)
        except subprocess.TimeoutExpired as exc:raise HTTPException(504,'DNS RPC timed out. Refresh the zone before retrying a write.') from exc
    try:result=json.loads(r.stdout)
    except ValueError as exc:raise HTTPException(502,'DNS RPC could not read the server response.') from exc
    if r.returncode or result.get('ok') is not True:
        code=result.get('code')
        if code in (5,0x80070005):raise HTTPException(403,'DNS denied this operation to your domain account. Your existing DNS permissions apply; no permissions were changed.')
        if code in (9711,9709,9601):raise HTTPException(409,f'DNS record or zone conflict (server code {code}). Refresh the zone before retrying.')
        raise HTTPException(502,f'DNS RPC failed (server code {code if code is not None else "unavailable"}). Check DNS management RPC ports and server configuration.')
    return result
