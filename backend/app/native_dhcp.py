"""Direct Microsoft DHCP RPC management with Kerberos and packet privacy."""
import ipaddress
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from fastapi import HTTPException
from impacket.dcerpc.v5 import dhcpm as d,epm,transport
from impacket.dcerpc.v5.rpcrt import RPC_C_AUTHN_GSS_NEGOTIATE,RPC_C_AUTHN_LEVEL_PKT_PRIVACY,DCERPCException
from impacket.dcerpc.v5.ndr import NDRCALL,NDRSTRUCT,NDRPOINTER,NDRUNION,NDRUniConformantArray
from impacket.dcerpc.v5.dtypes import DWORD,LPWSTR,NULL
from impacket.krb5.ccache import CCache
from .kerberos_cache import credential_cache


def ip_int(value):return int(ipaddress.IPv4Address(value))
def ip_text(value):return str(ipaddress.IPv4Address(int(value)))
def text(value):return value.rstrip('\x00') if isinstance(value,str) else ''

def pointer(cls):
    return type('P'+cls.__name__,(NDRPOINTER,),{'referent':(('Data',cls),)})

# [MS-DHCPM] classic dhcpsrv wire types. Impacket provides the transport,
# Kerberos, NDR machinery and most client types; these add missing calls.
class Reservation(NDRSTRUCT):
    structure=(('ReservedIpAddress',DWORD),('ReservedForClient',pointer(d.DHCP_BINARY_DATA)))
class ElementUnion(NDRUNION):
    union={0:('IpRange',pointer(d.DHCP_IP_RANGE)),1:('SecondaryHost',pointer(d.DHCP_HOST_INFO)),2:('ReservedIp',pointer(Reservation)),3:('ExcludeIpRange',pointer(d.DHCP_IP_RANGE)),4:('IpUsedCluster',pointer(d.DHCP_IP_CLUSTER))}
class Element(NDRSTRUCT):
    structure=(('ElementType',d.DHCP_SUBNET_ELEMENT_TYPE),('Element',ElementUnion))
class ElementArray(NDRUniConformantArray):item=Element
class ElementInfo(NDRSTRUCT):structure=(('NumElements',DWORD),('Elements',pointer(ElementArray)))
class Subnets(NDRCALL):
    opnum=3
    structure=(('ServerIpAddress',LPWSTR),('ResumeHandle',DWORD),('PreferredMaximum',DWORD))
class SubnetsResponse(NDRCALL):
    structure=(('ResumeHandle',DWORD),('EnumInfo',pointer(d.DHCP_IP_ARRAY)),('EnumRead',DWORD),('EnumTotal',DWORD),('ErrorCode',DWORD))
class Elements(NDRCALL):
    opnum=5
    structure=(('ServerIpAddress',LPWSTR),('SubnetAddress',DWORD),('EnumElementType',d.DHCP_SUBNET_ELEMENT_TYPE),('ResumeHandle',DWORD),('PreferredMaximum',DWORD))
class ElementsResponse(NDRCALL):
    structure=(('ResumeHandle',DWORD),('EnumElementInfo',pointer(ElementInfo)),('ElementsRead',DWORD),('ElementsTotal',DWORD),('ErrorCode',DWORD))
class Clients(NDRCALL):
    opnum=47
    structure=(('ServerIpAddress',LPWSTR),('SubnetAddress',DWORD),('ResumeHandle',DWORD),('PreferredMaximum',DWORD))
class ClientsResponse(NDRCALL):
    structure=(('ResumeHandle',DWORD),('ClientInfo',d.LPDHCP_CLIENT_INFO_ARRAY_VQ),('ClientsRead',DWORD),('ClientsTotal',DWORD),('ErrorCode',DWORD))
class CreateSubnet(NDRCALL):
    opnum=0
    structure=(('ServerIpAddress',LPWSTR),('SubnetAddress',DWORD),('SubnetInfo',d.DHCP_SUBNET_INFO))
class CreateSubnetResponse(NDRCALL):structure=(('ErrorCode',DWORD),)
class SetSubnet(NDRCALL):opnum=1;structure=CreateSubnet.structure
class SetSubnetResponse(NDRCALL):structure=(('ErrorCode',DWORD),)
class AddElement(NDRCALL):opnum=4;structure=(('ServerIpAddress',LPWSTR),('SubnetAddress',DWORD),('AddElementInfo',Element))
class AddElementResponse(NDRCALL):structure=(('ErrorCode',DWORD),)
class RemoveElement(NDRCALL):opnum=6;structure=(('ServerIpAddress',LPWSTR),('SubnetAddress',DWORD),('RemoveElementInfo',Element),('ForceFlag',DWORD))
class RemoveElementResponse(NDRCALL):structure=(('ErrorCode',DWORD),)
class DeleteSubnet(NDRCALL):opnum=7;structure=(('ServerIpAddress',LPWSTR),('SubnetAddress',DWORD),('ForceFlag',DWORD))
class DeleteSubnetResponse(NDRCALL):structure=(('ErrorCode',DWORD),)
class SetOption(NDRCALL):opnum=12;structure=(('ServerIpAddress',LPWSTR),('OptionID',DWORD),('ScopeInfo',d.DHCP_OPTION_SCOPE_INFO),('OptionValue',d.DHCP_OPTION_DATA))
class SetOptionResponse(NDRCALL):structure=(('ErrorCode',DWORD),)
class SetClient(NDRCALL):opnum=33;structure=(('ServerIpAddress',LPWSTR),('ClientInfo',d.DHCP_CLIENT_INFO_V4))
class SetClientResponse(NDRCALL):structure=(('ErrorCode',DWORD),)


def invoke(rpc,call):
    call['ServerIpAddress']=NULL
    return rpc.request(call,checkError=False)


def checked(response):
    code=int(response['ErrorCode'])
    if code==5:raise HTTPException(403,'DHCP denied this operation for your domain account. DHCP Users can read; DHCP Administrators can manage. No permissions were changed.')
    if code not in (0,234,259):raise HTTPException(422,f'DHCP returned error {code}. Refresh the server before retrying a write.')
    return code


def pages(rpc,cls,field,rows_key,**kwargs):
    resume=0;rows=[]
    while True:
        call=cls()
        for key,value in kwargs.items():call[key]=value
        call['ResumeHandle']=resume;call['PreferredMaximum']=262144
        response=invoke(rpc,call);status=checked(response)
        if status==259:break
        info=response[field]
        if hasattr(info,'fields') and info.fields.get('ReferentID',1)!=0:
            rows.extend(info[rows_key])
        if status==0:break
        next_resume=int(response['ResumeHandle'])
        if next_resume<=resume:raise HTTPException(502,'DHCP returned a stalled enumeration cursor; partial results are not shown.')
        resume=next_resume
    return rows


@contextmanager
def connection(cfg,host):
    rpc=None
    try:
        with credential_cache(cfg) as env:
            realm=cfg['domain'].upper();user=cfg['username'].split('@')[0].split('\\')[-1]
            cache=CCache.loadFile(env['KRB5CCNAME'][5:])
            tgt=cache.getCredential('krbtgt/'+realm+'@'+realm).toTGT()
            # EPM lookup is anonymous metadata only. Credentials are used in the
            # following mutually authenticated Kerberos RPC bind, never NTLM.
            binding=epm.hept_map(host,d.MSRPC_UUID_DHCPSRV,protocol='ncacn_ip_tcp')
            channel=transport.DCERPCTransportFactory(binding)
            channel.setRemoteName(host)
            channel.set_connect_timeout(5)
            channel.set_credentials(user,'',realm,TGT=tgt)
            channel.set_kerberos(True,kdcHost=cfg.get('preferred_dc') or host)
            rpc=channel.get_dce_rpc();rpc.set_auth_type(RPC_C_AUTHN_GSS_NEGOTIATE);rpc.set_auth_level(RPC_C_AUTHN_LEVEL_PKT_PRIVACY)
            rpc.connect();rpc.bind(d.MSRPC_UUID_DHCPSRV)
            yield rpc
    except HTTPException:raise
    except DCERPCException as exc:
        if exc.get_error_code() in (5,0x80070005):raise HTTPException(403,'DHCP RPC denied access to your domain account.') from exc
        raise HTTPException(502,'Direct DHCP RPC failed. Check port 135, dynamic RPC ports and the DHCP service. No WinRM or Windows worker is used.') from exc
    except Exception as exc:
        raise HTTPException(502,'Direct DHCP connection or response failed. Check the selected DHCP server, VPN and RPC connectivity.') from exc
    finally:
        if rpc:
            try:rpc.disconnect()
            except Exception:pass


def subnet_info(rpc,scope):
    call=d.DhcpGetSubnetInfo();call['SubnetAddress']=scope
    response=invoke(rpc,call);checked(response)
    return response['SubnetInfo']


def scopes(rpc):
    result=[]
    for subnet in pages(rpc,Subnets,'EnumInfo','Elements'):
        subnet=int(subnet["Data"] if hasattr(subnet,"fields") else subnet);info=subnet_info(rpc,subnet)
        ranges=pages(rpc,Elements,'EnumElementInfo','Elements',SubnetAddress=subnet,EnumElementType=0)
        starts=[int(x['Element']['IpRange']['StartAddress']) for x in ranges]
        ends=[int(x['Element']['IpRange']['EndAddress']) for x in ranges]
        state=int(info['SubnetState'])
        result.append({'scopeId':ip_text(subnet),'name':text(info['SubnetName']),'state':'Active' if state in (0,2) else 'Inactive','startRange':ip_text(min(starts)) if starts else '', 'endRange':ip_text(max(ends)) if ends else '', 'subnetMask':ip_text(info['SubnetMask']),'description':text(info['SubnetComment']),'free':None,'inUse':None})
    return result


def byte_data(data):
    return b''.join(bytes([x]) if isinstance(x,int) else x for x in data)


def leases(rpc,scope):
    rows=pages(rpc,Clients,'ClientInfo','Clients',SubnetAddress=scope)
    result=[]
    for row in rows:
        raw=byte_data(row['ClientHardwareAddress']['Data_'])
        expires=row['ClientLeaseExpires'];number=(int(expires['dwHighDateTime'])<<32)|int(expires['dwLowDateTime'])
        expiry='Never' if number>=0x7fffffffffffffff else (datetime(1601,1,1,tzinfo=timezone.utc)+timedelta(microseconds=number//10)).isoformat() if number else ''
        result.append({'scopeId':ip_text(scope),'ipAddress':ip_text(row['ClientIpAddress']),'hostName':text(row['ClientName']),'clientId':raw[5:].hex('-') if len(raw)>5 and raw[:4]==scope.to_bytes(4,'little') and raw[4]==1 else raw.hex('-'),'description':text(row['ClientComment']),'state':{0:'Offered',1:'Active',2:'Declined',3:'Doom'}.get(int(row['AddressState'])&3,'Unknown')+(' / Reservation' if int(row['bClientType'])&4 else ''),'expiry':expiry})
    return result


def reservations(rpc,scope):
    result=[]
    clients={x['ipAddress']:x for x in leases(rpc,scope)}
    for element in pages(rpc,Elements,'EnumElementInfo','Elements',SubnetAddress=scope,EnumElementType=2):
        reservation=element['Element']['ReservedIp'];raw=byte_data(reservation['ReservedForClient']['Data_'])
        result.append({'scopeId':ip_text(scope),'ipAddress':ip_text(reservation['ReservedIpAddress']),'clientId':raw[5:].hex('-') if len(raw)>5 and raw[:4]==scope.to_bytes(4,'little') and raw[4]==1 else raw.hex('-'),'name':clients.get(ip_text(reservation['ReservedIpAddress']),{}).get('hostName',''),'description':clients.get(ip_text(reservation['ReservedIpAddress']),{}).get('description','')})
    return result


def request(cfg,host,method,path,payload=None,params=None):
    body=payload or {};params=params or {}
    try:
        if method=='GET' and path in ('/dhcp/leases','/dhcp/reservations') and not params.get('scope_id'):raise HTTPException(422,'Select a DHCP scope first.')
        with connection(cfg,host) as rpc:
            if method=='GET':
                if path=='/dhcp/scopes':return scopes(rpc)
                scope=ip_int(params['scope_id'])
                if path=='/dhcp/leases':return leases(rpc,scope)
                if path=='/dhcp/reservations':return reservations(rpc,scope)
            return write(rpc,path,body)
    except (ValueError,KeyError) as exc:raise HTTPException(422,'Invalid DHCP address, scope or operation parameters.') from exc


def send_write(rpc,call):
    response=invoke(rpc,call)
    checked(response)
    if int(response['ErrorCode'])!=0:raise HTTPException(502,'DHCP did not confirm the write. Refresh before retrying.')


def scope_geometry(body):
    start=ipaddress.IPv4Address(body['start_range']);end=ipaddress.IPv4Address(body['end_range'])
    network=ipaddress.IPv4Network((str(start),body['subnet_mask']),strict=False)
    if end not in network or start>end or start==network.network_address or end==network.broadcast_address:raise HTTPException(422,'DHCP range must contain usable addresses in a single subnet.')
    return network,int(start),int(end)


def write(rpc,path,body):
    if path=='/dhcp/scopes':
        network,start,end=scope_geometry(body);subnet=int(network.network_address)
        call=CreateSubnet();call['SubnetAddress']=subnet
        info=call['SubnetInfo'];info['SubnetAddress']=subnet;info['SubnetMask']=int(network.netmask)
        info['SubnetName']=body['name']+'\0';info['SubnetComment']=body.get('description','')+'\0'
        info['PrimaryHost']['IpAddress']=0;info['PrimaryHost']['NetBiosName']=NULL;info['PrimaryHost']['HostName']=NULL;info['SubnetState']=1
        send_write(rpc,call)
        try:
            add=AddElement();add['SubnetAddress']=subnet;add['AddElementInfo']['ElementType']=0;add['AddElementInfo']['Element']['tag']=0
            add['AddElementInfo']['Element']['IpRange']['StartAddress']=start;add['AddElementInfo']['Element']['IpRange']['EndAddress']=end
            send_write(rpc,add)
            option=SetOption();option['OptionID']=51;option['ScopeInfo']['ScopeType']=2;option['ScopeInfo']['ScopeInfo']['tag']=2;option['ScopeInfo']['ScopeInfo']['SubnetScopeInfo']=subnet
            option['OptionValue']['NumElements']=1
            value=d.DHCP_OPTION_DATA_ELEMENT();value['OptionType']=2;value['Element']['tag']=2;value['Element']['DWordOption']=int(body.get('lease_days',8))*86400
            option['OptionValue']['Elements']=[value];send_write(rpc,option)
            if body.get('state','Active')=='Active':
                change=SetSubnet();change['SubnetAddress']=subnet;change['SubnetInfo']=subnet_info(rpc,subnet);change['SubnetInfo']['SubnetState']=0;send_write(rpc,change)
        except Exception as exc:raise HTTPException(502,'Scope was created, but configuration did not finish. Refresh and inspect its range, lease duration and state before retrying. No automatic rollback was performed.') from exc
        return {'ok':True,'scope_id':str(network.network_address)}
    scope=ip_int(body['scope_id'])
    if path=='/dhcp/scopes/state':
        call=SetSubnet();call['SubnetAddress']=scope;call['SubnetInfo']=subnet_info(rpc,scope);call['SubnetInfo']['SubnetState']=0 if body['state']=='Active' else 1
        send_write(rpc,call);return {'ok':True}
    if path=='/dhcp/scopes/delete':
        call=DeleteSubnet();call['SubnetAddress']=scope;call['ForceFlag']=0
        send_write(rpc,call);return {'ok':True}
    if path=='/dhcp/reservations/delete':
        address=ip_int(body['ip_address'])
        elements=pages(rpc,Elements,'EnumElementInfo','Elements',SubnetAddress=scope,EnumElementType=2)
        element=next((x for x in elements if int(x['Element']['ReservedIp']['ReservedIpAddress'])==address),None)
        if element is None:raise HTTPException(404,'DHCP reservation no longer exists. Refresh the scope.')
        call=RemoveElement();call['SubnetAddress']=scope;call['RemoveElementInfo']=element;call['ForceFlag']=1
        send_write(rpc,call);return {'ok':True}
    if path=='/dhcp/reservations':
        import re
        address=ip_int(body['ip_address']);info=subnet_info(rpc,scope)
        if address & int(info['SubnetMask'])!=scope:raise HTTPException(422,'Reservation IP is outside the selected subnet.')
        identifier=re.sub('[:-]','',body['client_id'])
        if not re.fullmatch(r'[0-9a-fA-F]{12}',identifier):raise HTTPException(422,'Enter a six-byte MAC address, such as 00-11-22-33-44-55.')
        raw=bytes.fromhex(identifier)
        call=AddElement();call['SubnetAddress']=scope;call['AddElementInfo']['ElementType']=2;call['AddElementInfo']['Element']['tag']=2
        reservation=call['AddElementInfo']['Element']['ReservedIp'];reservation['ReservedIpAddress']=address
        reservation['ReservedForClient']['DataLength']=len(raw);reservation['ReservedForClient']['Data_']=[bytes([x]) for x in raw]
        send_write(rpc,call)
        if body.get('name') or body.get('description'):
            try:
                query=d.DhcpGetClientInfoV4();query['SearchInfo']['SearchType']=0;query['SearchInfo']['SearchInfo']['tag']=0;query['SearchInfo']['SearchInfo']['ClientIpAddress']=address
                response=invoke(rpc,query);checked(response)
                client=SetClient();client['ClientInfo']=response['ClientInfo'];client['ClientInfo']['ClientName']=body.get('name','')+'\0';client['ClientInfo']['ClientComment']=body.get('description','')+'\0'
                send_write(rpc,client)
            except Exception as exc:raise HTTPException(502,'Reservation was created, but its name/description was not saved. Refresh before retrying.') from exc
        return {'ok':True}
    raise HTTPException(501,'Unsupported direct DHCP operation')
