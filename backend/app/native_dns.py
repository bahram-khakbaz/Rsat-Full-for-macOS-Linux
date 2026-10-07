"""Read AD-integrated DNS without PowerShell, using authenticated LDAPS."""
import ipaddress
import struct
import shlex
from fastapi import HTTPException
from ldap3 import BASE,LEVEL
from ldap3.core.exceptions import LDAPException
from .native_ad import Directory,scalar,values

def counted_name(data):
    if len(data)<2:raise ValueError('Truncated DNS name')
    length,count=data[:2]
    if length+2!=len(data):raise ValueError('Invalid DNS name length')
    if length==0 and count==0:return '.'
    if data[-1]!=0:raise ValueError('DNS name must be null terminated')
    offset=2;labels=[]
    for _ in range(count):
        if offset>=len(data):raise ValueError('Truncated DNS label')
        size=data[offset];offset+=1
        if not size or offset+size>len(data):raise ValueError('Invalid DNS label')
        labels.append(data[offset:offset+size].decode('ascii'));offset+=size
    if offset!=len(data)-1:raise ValueError('Trailing DNS name data')
    return '.'.join(labels)+'.'

def decode_record(raw):
    if not isinstance(raw,bytes) or len(raw)<24:raise ValueError('Invalid DNS record')
    length,kind=struct.unpack_from('<HH',raw)
    if raw[4]!=5 or len(raw)!=24+length:raise ValueError('Invalid DNS record header')
    ttl=struct.unpack_from('>I',raw,12)[0];data=raw[24:]
    names={1:'A',28:'AAAA',5:'CNAME',12:'PTR',2:'NS',33:'SRV',16:'TXT',15:'MX',6:'SOA'}
    if kind==1:value=str(ipaddress.IPv4Address(data))
    elif kind==28:value=str(ipaddress.IPv6Address(data))
    elif kind in (5,12,2):value=counted_name(data)
    elif kind==33:
        if len(data)<8:raise ValueError('Truncated SRV')
        priority,weight,port=struct.unpack_from('>HHH',data);value=f'{priority} {weight} {port} {counted_name(data[6:])}'
    elif kind==15:value=str(struct.unpack_from('>H',data)[0])+' '+counted_name(data[2:])
    elif kind==16:
        labels=[];i=0
        while i<len(data):
            size=data[i];i+=1
            if i+size>len(data):raise ValueError('Truncated TXT')
            labels.append(data[i:i+size].decode('utf-8',errors='replace'));i+=size
        value=shlex.join(labels)
    else:value='HEX: '+data.hex() # Display unimplemented record data explicitly, never drop it.
    return {'type':names.get(kind,'TYPE'+str(kind)),'value':value,'ttl':ttl}

def zone_rows(directory):
    roots=directory.search('','(objectClass=*)',['namingContexts'],BASE)
    bases=['CN=MicrosoftDNS,'+x for x in values(roots[0],'namingContexts') if x.lower().startswith(('dc=domaindnszones,','dc=forestdnszones,'))]
    bases.append('CN=MicrosoftDNS,CN=System,'+directory.base)
    rows=[];seen=set()
    for base in bases:
        try:result=directory.search(base,'(objectClass=dnsZone)',['name'],LEVEL)
        except HTTPException:
            if (directory.conn.result or {}).get('result')==32:continue
            raise
        for r in result:
            name=scalar(r,'name')
            if name.lower() in seen or name=='RootDNSServers':continue
            seen.add(name.lower())
            rows.append({'name':name,'type':'AD-integrated / LDAP inventory','integrated':True,'reverse':name.lower().endswith(('.in-addr.arpa','.ip6.arpa')),'dn':r['dn'],'source':'LDAPS'})
    return sorted(rows,key=lambda r:r['name'].lower())

def request(path,params=None):
    try:return _request(path,params)
    except (LDAPException,OSError) as exc:
        raise HTTPException(504,'DNS inventory read timed out or disconnected. No partial results are shown; refresh after checking VPN.') from exc

def _request(path,params=None):
    with Directory() as directory:
        # Binding remains short; a large DNS zone needs more than four seconds
        # for each response page on a busy DC or VPN connection.
        directory.conn.socket.settimeout(30)
        directory.conn.receive_timeout=30
        zones=zone_rows(directory)
        if path=='/dns/zones':return zones
        zone=(params or {}).get('zone','')
        selected=[x for x in zones if x['name'].lower()==zone.lower()]
        if not selected:raise HTTPException(404,'Select an AD-integrated DNS zone')
        records=[]
        for z in selected:
            nodes=directory.search(z['dn'],'(&(objectClass=dnsNode)(!(dNSTombstoned=TRUE)))',['name','dnsRecord'],LEVEL)
            for node in nodes:
                for raw in values(node,'dnsRecord'):
                    try:record=decode_record(raw)
                    except (ValueError,struct.error,UnicodeError) as exc:
                        raise HTTPException(502,'An AD DNS record could not be decoded. No partial inventory is shown.') from exc
                    records.append({'zone':z['name'],'name':scalar(node,'name'),**record})
        return records

def dhcp_servers():
    with Directory() as d:
        rows=d.search('CN=NetServices,CN=Services,'+d.config_base,'(dhcpServers=*)',['name','dhcpServers'])
        result=[];seen=set()
        for row in rows:
            for value in values(row,'dhcpServers'):
                parts=value.split('$');host=next((x[1:] for x in parts if x.startswith('s')),'');ip=next((x[1:] for x in parts if x.startswith('i')),'')
                if host and host.lower() not in seen:
                    seen.add(host.lower());result.append({'host':host,'ip':ip,'authorized':True})
        return sorted(result,key=lambda x:x['host'])
