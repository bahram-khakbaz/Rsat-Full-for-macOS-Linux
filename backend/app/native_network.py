"""Direct DNS/DHCP RPC and optional WinRM; Kerberos mutual authentication.
No worker, credential delegation, NTLM fallback, or unencrypted application data.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import winrm
from fastapi import HTTPException
from .db import SessionLocal, SystemSetting
from .native_ad import configuration
from .network_scripts import SCRIPTS, DNS_CREATE

_lock=threading.Lock()
_auth_failures=set()

def reset_auth_failure():
    with _lock:_auth_failures.clear()

def configuration_network():
    cfg=configuration()
    with SessionLocal() as db:
        row=db.query(SystemSetting).filter_by(key='native_network').first()
        extra=json.loads(row.value) if row else {}
    preferred=cfg.get('preferred_dc') or next(iter(cfg.get('hosts',[])),'')
    return cfg, {'dns_host':extra.get('dns_host') or preferred,'dhcp_host':extra.get('dhcp_host') or preferred,'port':extra.get('port',5985),'dns_mode':extra.get('dns_mode','Direct'),'dhcp_mode':extra.get('dhcp_mode','RPC')}

def build_script(method,path,payload=None,params=None):
    data=dict(params or {});data.update(payload or {})
    script=SCRIPTS.get((method,path))
    if (method,path)==('POST','/dns/records'):script=DNS_CREATE.get(data.get('type'))
    if not script:raise HTTPException(501,'Unsupported direct network operation')
    # Allowlisted variable names; values never become PowerShell source.
    if any(not re.fullmatch('[a-z_]+',key) for key in data):raise HTTPException(422,'Invalid parameter name')
    encoded=base64.b64encode(json.dumps(data,ensure_ascii=False).encode()).decode()
    header="$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    header+="$inputData=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"')) | ConvertFrom-Json); "
    header+="foreach($p in $inputData.PSObject.Properties){[Environment]::SetEnvironmentVariable(('RSAT_'+$p.Name.ToUpperInvariant()),[string]$p.Value,'Process')}; "
    # ConvertTo-Json sees no pipeline object for empty reads: [] is normalized below.
    return header+script

def request(method,path,payload=None,params=None):
    cfg,network=configuration_network()
    service=path.split('/')[1]
    host=network.get(service+'_host','').lower()
    domain=cfg.get('domain','').lower()
    if not domain or not host.endswith('.'+domain) or not re.fullmatch(r'[a-z0-9.-]+',host):
        raise HTTPException(409,'Configure a DNS/DHCP server FQDN in this domain under Service connection.')
    if path.startswith('/dhcp/') and network['dhcp_mode']=='RPC':
        from .native_dhcp import request as dhcp_rpc
        return dhcp_rpc(cfg,network['dhcp_host'],method,path,payload,params)
    if path.startswith('/dns/') and network['dns_mode']=='Direct':
        if method=='GET':
            from .native_dns import request as ldap_dns
            return ldap_dns(path,params)
        if path in ('/dns/records','/dns/records/delete','/dns/records/update'):
            from .dns_rpc import request as dns_rpc
            return dns_rpc(cfg,network['dns_host'],payload,delete=path.endswith('/delete'),update=path.endswith('/update'))
        raise HTTPException(409,'Direct mode supports DNS records. Zone creation and deletion require WinRM management mode.')
    if path.startswith('/dns/') and network['dns_mode']=='LDAP':
        if method!='GET':raise HTTPException(409,'LDAP DNS inventory is read-only. Select WinRM management and test its permissions before changing records.')
        from .native_dns import request as ldap_dns
        return ldap_dns(path,params)
    script=build_script(method,path,payload,params)
    service=path.split('/')[1]
    host=network.get(service+'_host','').lower()
    domain=cfg.get('domain','').lower()
    if not domain or not host or not host.endswith('.'+domain) or not re.fullmatch(r'[a-z0-9.-]+',host):
        raise HTTPException(409,'Configure a DNS/DHCP server FQDN in this domain under Service connection.')
    if not cfg.get('username') or not cfg.get('password'):raise HTTPException(409,'Save the domain account under Settings first.')
    realm=domain.upper()
    user=cfg['username'].split('@')[0].split('\\')[-1]+'@'+realm
    key=hashlib.sha256((user+'\0'+cfg['password']).encode()).hexdigest()
    kdc=cfg.get('preferred_dc') or host
    if not re.fullmatch(r'[a-zA-Z0-9.-]+',kdc):raise HTTPException(422,'Invalid KDC name')
    # libkrb5 reads process env. Serialize all service calls and restore env; no
    # other connector uses the cache. Each temporary cache is private and removed.
    with _lock:
        if key in _auth_failures:raise HTTPException(422,'Kerberos rejected these credentials. Re-save Service connection or update the domain password before retrying.')
        with tempfile.TemporaryDirectory(prefix='rsat-kerberos-') as directory:
            config_path=directory+'/krb5.conf';cache='FILE:'+directory+'/ticket'
            with open(config_path,'w') as f:
                f.write('[libdefaults]\n default_realm = '+realm+'\n dns_lookup_kdc = false\n dns_lookup_realm = false\n rdns = false\n udp_preference_limit = 1\n[realms]\n '+realm+' = {\n  kdc = '+kdc+'\n }\n')
            env=os.environ.copy();env.update(KRB5_CONFIG=config_path,KRB5CCNAME=cache)
            try:
                acquired=subprocess.run(['kinit','-l','5m',user],input=cfg['password']+'\n',capture_output=True,text=True,env=env,timeout=12)
            except subprocess.TimeoutExpired as exc:
                raise HTTPException(504,'Kerberos KDC timed out. Check VPN and TCP port 88.') from exc
            if acquired.returncode:
                err=acquired.stderr.lower()
                if 'preauthentication failed' in err or 'password incorrect' in err:_auth_failures.add(key)
                raise HTTPException(502,'Kerberos login failed. Check domain credentials, clock, VPN and KDC port 88. No NTLM fallback was attempted.')
            previous={key:os.environ.get(key) for key in ('KRB5_CONFIG','KRB5CCNAME')}
            os.environ.update(KRB5_CONFIG=config_path,KRB5CCNAME=cache)
            session=None
            try:
                session=winrm.Session('http://'+host+':'+str(network['port'])+'/wsman',auth=(user,None),transport='kerberos',message_encryption='always',kerberos_delegation=False,read_timeout_sec=50,operation_timeout_sec=40,proxy=None)
                response=session.run_ps(script)
                if response.status_code:
                    # Fixed operations never contain passwords. Do not expose raw
                    # PowerShell output, which may contain infrastructure details.
                    raise HTTPException(502,f'{service.upper()} command failed on {host}. Verify WinRM permissions and the {"DnsServer" if service=="dns" else "DhcpServer"} PowerShell module on this service host. Refresh before retrying a write.')
                raw=response.std_out.decode('utf-8-sig').strip()
                if len(raw.encode())>32*1024*1024:raise HTTPException(413,'Service output too large. Select one zone or scope.')
                if not raw:
                    if method=='GET':return []
                    raise HTTPException(502,'Service returned no write confirmation. Refresh before retrying.')
                result=json.loads(raw)
                if method=='GET':return result if isinstance(result,list) else [result]
                if not isinstance(result,dict) or result.get('ok') is not True:raise HTTPException(502,'Service returned an invalid write confirmation.')
                return result
            except HTTPException:raise
            except winrm.exceptions.InvalidCredentialsError as exc:
                raise HTTPException(403,f'Kerberos domain login succeeded, but {host} rejected WinRM access. Verify remote management permission and WinRM authentication policy on this service server. This is separate from AD/RSAT permissions.') from exc
            except Exception as exc:
                raise HTTPException(502,f'Direct {service.upper()} connection failed on {host}. Check WinRM port {network["port"]}, Kerberos HTTP service identity and account permissions. No worker or NTLM fallback was used.') from exc
            finally:
                if session:session.protocol.transport.close_session()
                for key,value in previous.items():
                    if value is None:os.environ.pop(key,None)
                    else:os.environ[key]=value
