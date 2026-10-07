"""Private short-lived Kerberos credentials for direct service operations."""
import hashlib
import os
import re
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from fastapi import HTTPException

_lock=threading.Lock()
_failures=set()

@contextmanager
def credential_cache(cfg):
    domain=cfg.get('domain','').upper()
    username=cfg.get('username','').split('@')[0].split('\\')[-1]
    kdc=cfg.get('preferred_dc') or next(iter(cfg.get('hosts',[])),'')
    password=cfg.get('password','')
    if not domain or not username or not password:raise HTTPException(409,'Save your domain account in Settings first.')
    if not re.fullmatch(r'[A-Z0-9.-]+',domain) or not re.fullmatch(r'[a-zA-Z0-9.-]+',kdc):raise HTTPException(422,'Invalid domain or KDC hostname')
    key=hashlib.sha256((username+'@'+domain+'\0'+password).encode()).hexdigest()
    with _lock:
        if key in _failures:raise HTTPException(422,'AD rejected these credentials. Update the saved domain password before retrying.')
        with tempfile.TemporaryDirectory(prefix='rsat-service-') as directory:
            path=directory+'/krb5.conf'
            with open(path,'w') as f:f.write('[libdefaults]\n default_realm = '+domain+'\n dns_lookup_kdc = false\n rdns = false\n udp_preference_limit = 1\n[realms]\n '+domain+' = {\n kdc = '+kdc+'\n }\n')
            env=os.environ.copy();env.update(KRB5_CONFIG=path,KRB5CCNAME='FILE:'+directory+'/ticket')
            try:r=subprocess.run(['kinit','-l','5m',username+'@'+domain],input=password+'\n',text=True,capture_output=True,env=env,timeout=12)
            except subprocess.TimeoutExpired as exc:raise HTTPException(504,'Kerberos KDC timed out. Check VPN and port 88.') from exc
            if r.returncode:
                if any(x in r.stderr.lower() for x in ('preauthentication failed','password incorrect')):_failures.add(key)
                raise HTTPException(502,'Kerberos login failed. Check saved domain account, time and VPN.')
            yield env
