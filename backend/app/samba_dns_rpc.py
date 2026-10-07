"""Runs with Debian's Python and Samba bindings, in a credential-cache subprocess."""
import json
import os
import sys
import shlex
from samba.param import LoadParm
from samba.credentials import Credentials,MUST_USE_KERBEROS,SPECIFIED
from samba.dcerpc import dnsserver,dnsp
from samba.dnsserver import ARecord,AAAARecord,CNAMERecord,PTRRecord,NSRecord,MXRecord,SRVRecord,TXTRecord


def connect(host,lp,creds):
    # Certain Windows endpoints intermittently reject a fresh authenticated
    # bind with STATUS_INVALID_PARAMETER. Retry that negotiation only.
    # No DNS query or write has been sent, and write calls are never retried.
    for attempt in range(5):
        try:return dnsserver.dnsserver('ncacn_ip_tcp:'+host+'[seal]',lp,creds)
        except Exception as exc:
            if not exc.args or exc.args[0]!=0xc000000d or attempt==4:raise


def record(kind,value,ttl):
    if kind=='MX':
        priority,target=value.split();return MXRecord(target,int(priority),ttl=ttl)
    if kind=='SRV':
        priority,weight,port,target=value.split();return SRVRecord(target,int(port),int(priority),int(weight),ttl=ttl)
    if kind=='TXT':
        r=TXTRecord(shlex.split(value),ttl=ttl)
        for segment in r.data.str:segment.len=len(segment.str.encode('utf-8'))
        return r
    return {'A':ARecord,'AAAA':AAAARecord,'CNAME':CNAMERecord,'PTR':PTRRecord,'NS':NSRecord}[kind](value,ttl=ttl)


stage='input'

def main():
    global stage
    body=json.load(sys.stdin)
    lp=LoadParm();lp.load_default()
    creds=Credentials();creds.guess(lp)
    creds.set_named_ccache(os.environ['KRB5CCNAME'],SPECIFIED)
    creds.set_kerberos_state(MUST_USE_KERBEROS)
    host=body['host'];zone=body['zone']
    stage='bind'
    connection=connect(host,lp,creds)
    version=dnsserver.DNS_CLIENT_VERSION_LONGHORN
    stage=body['operation']
    if body['operation']=='probe':
        connection.DnssrvEnumRecords2(version,0,host,zone,'@',None,dnsp.DNS_TYPE_SOA,dnsserver.DNS_RPC_VIEW_AUTHORITY_DATA,None,None)
    else:
        buffer=dnsserver.DNS_RPC_RECORD_BUF();buffer.rec=record(body['type'],body['value'],body['ttl'])
        add=buffer if body['operation'] in ('add','update') else None
        remove=buffer if body['operation']=='delete' else None
        if body['operation']=='update':
            remove=dnsserver.DNS_RPC_RECORD_BUF();remove.rec=record(body['type'],body['old_value'],body['old_ttl'])
        connection.DnssrvUpdateRecord2(version,0,host,zone,body['name'],add,remove)
    print(json.dumps({'ok':True,'server':host,'authentication':'Kerberos / encrypted DNS RPC'}))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Send only the numeric protocol error, never credentials or ticket data.
        code=exc.args[0] if exc.args and isinstance(exc.args[0],int) else None
        print(json.dumps({'ok':False,'code':code,'error_type':type(exc).__name__,'stage':stage}))
        sys.exit(1)
