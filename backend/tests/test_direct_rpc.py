import json
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app import native_dhcp as dhcp,dns_rpc,native_network
from impacket.dcerpc.v5 import dhcpm as d

class FakeRPC:
    def __init__(self,fail=None):self.calls=[];self.fail=fail
    def request(self,call,checkError=False):
        call.getData()  # Serialize the real NDR request, not a dictionary mock.
        self.calls.append(call)
        if isinstance(call,d.DhcpGetSubnetInfo):
            result=d.DhcpGetSubnetInfoResponse();info=result['SubnetInfo']
            info['SubnetAddress']=dhcp.ip_int('192.0.2.0');info['SubnetMask']=dhcp.ip_int('255.255.255.0')
            info['SubnetName']='Existing\0';info['SubnetComment']='Keep this\0';info['SubnetState']=1
            result['ErrorCode']=0
            return result
        return {'ErrorCode':5 if isinstance(call,self.fail or ()) else 0}


def test_scope_create_serializes_inactive_then_range_lease_then_activation():
    rpc=FakeRPC()
    assert dhcp.write(rpc,'/dhcp/scopes',{'name':'Example','start_range':'192.0.2.10','end_range':'192.0.2.100','subnet_mask':'255.255.255.0','lease_days':8,'state':'Active'})['ok']
    assert [type(c) for c in rpc.calls]==[dhcp.CreateSubnet,dhcp.AddElement,dhcp.SetOption,d.DhcpGetSubnetInfo,dhcp.SetSubnet]
    assert rpc.calls[0]['SubnetInfo']['SubnetState']==1
    assert rpc.calls[2]['OptionValue']['Elements'][0]['Element']['DWordOption']==8*86400
    assert rpc.calls[-1]['SubnetInfo']['SubnetState']==0
    assert rpc.calls[-1]['SubnetInfo']['SubnetComment']=='Keep this\0'


def test_scope_partial_failure_does_not_repeat_or_rollback():
    rpc=FakeRPC(dhcp.AddElement)
    with pytest.raises(HTTPException) as err:dhcp.write(rpc,'/dhcp/scopes',{'name':'Example','start_range':'192.0.2.10','end_range':'192.0.2.100','subnet_mask':'255.255.255.0'})
    assert err.value.status_code==502 and 'was created' in err.value.detail
    assert len(rpc.calls)==2


def test_reservation_mac_wire_bytes_and_server_permission():
    rpc=FakeRPC()
    dhcp.write(rpc,'/dhcp/reservations',{'scope_id':'192.0.2.0','ip_address':'192.0.2.77','client_id':'00-11-22-33-44-55'})
    data=rpc.calls[-1]['AddElementInfo']['Element']['ReservedIp']['ReservedForClient']
    assert data['DataLength']==6 and dhcp.byte_data(data['Data_'])==bytes.fromhex('001122334455')
    denied=FakeRPC(dhcp.AddElement)
    with pytest.raises(HTTPException) as err:dhcp.write(denied,'/dhcp/reservations',{'scope_id':'192.0.2.0','ip_address':'192.0.2.77','client_id':'00-11-22-33-44-55'})
    assert err.value.status_code==403


def test_scope_state_preserves_other_server_fields():
    rpc=FakeRPC();dhcp.write(rpc,'/dhcp/scopes/state',{'scope_id':'192.0.2.0','state':'Active'})
    assert rpc.calls[-1]['SubnetInfo']['SubnetName']=='Existing\0'
    assert rpc.calls[-1]['SubnetInfo']['SubnetMask']==dhcp.ip_int('255.255.255.0')


def test_enumeration_stalled_cursor_never_returns_partial_results():
    class RPC:
        def request(self,*args,**kwargs):return {'ErrorCode':234,'EnumInfo':{'Elements':[1]},'ResumeHandle':0}
    with pytest.raises(HTTPException) as err:dhcp.pages(RPC(),dhcp.Subnets,'EnumInfo','Elements')
    assert err.value.status_code==502


@pytest.mark.parametrize('bad',[
    {'name':'evil\nname'}, {'value':'bad-address'}, {'ttl':0}, {'type':'SOA'}, {'zone':'x; command'},
])
def test_dns_rejects_bad_parameters_before_connecting(bad):
    with pytest.raises(HTTPException):dns_rpc.parameters('dc.example.com',{'zone':'example.com','name':'record','type':'A','value':'192.0.2.1',**bad})


def test_dns_fqdn_and_root_names():
    data={'zone':'example.com','name':'record.example.com.','type':'A','value':'192.0.2.1','ttl':123}
    result=dns_rpc.parameters('dc.example.com',data)
    assert result['name']=='record' and result['ttl']==123
    assert dns_rpc.parameters('dc.example.com',{**data,'name':'@'},delete=True)['operation']=='delete'


def test_dns_helper_has_private_cache_no_password_in_request(monkeypatch):
    @contextmanager
    def cache(cfg):yield {'KRB5CCNAME':'FILE:/private/test-ticket'}
    monkeypatch.setattr(dns_rpc,'credential_cache',cache)
    def run(args,**kwargs):
        assert 'secret' not in str(args)+kwargs['input']
        assert kwargs['env']['KRB5CCNAME']=='FILE:/private/test-ticket'
        assert json.loads(kwargs['input'])['operation']=='probe'
        return SimpleNamespace(stdout=json.dumps({'ok':False,'code':5}),returncode=1)
    monkeypatch.setattr(dns_rpc.subprocess,'run',run)
    with pytest.raises(HTTPException) as err:dns_rpc.request({'password':'secret'},'dc.example.com',{'zone':'example.com'},probe=True)
    assert err.value.status_code==403


def test_service_host_rejected_before_credentials(monkeypatch):
    monkeypatch.setattr(native_network,'configuration_network',lambda:({'domain':'example.com'},{'dns_host':'outside.invalid','dns_mode':'Direct'}))
    with pytest.raises(HTTPException) as err:native_network.request('POST','/dns/records',{})
    assert err.value.status_code==409


def test_dns_update_keeps_original_record_identity_and_zero_ttl():
    body={'zone':'example.com','name':'record','type':'A','value':'192.0.2.2','ttl':1200,'old_value':'192.0.2.1','old_ttl':0}
    result=dns_rpc.parameters('dc.example.com',body,update=True)
    assert result['operation']=='update' and result['old_value']=='192.0.2.1'
    assert result['value']=='192.0.2.2' and result['old_ttl']==0
    with pytest.raises(HTTPException):dns_rpc.parameters('dc.example.com',{**body,'old_value':'invalid'},update=True)

@pytest.mark.parametrize('kind,value', [('NS','ns.example.com.'),('MX','10 mx.example.com.'),('SRV','1 2 443 service.example.com.'),('TXT','"text with spaces" "second segment"')])
def test_extended_dns_values_validate_and_preserve_segments(kind,value):
    body={'zone':'example.com','name':'node','type':kind,'value':value}
    result=dns_rpc.parameters('dc.example.com',body)
    assert result['type']==kind
    if kind=='TXT':
        import shlex
        assert shlex.split(result['value'])==['text with spaces','second segment']

@pytest.mark.parametrize('kind,value',[('MX','65536 mx.example.com'),('SRV','1 2 -1 host.example.com'),('TXT','"'+ 'x'*256 +'"')])
def test_extended_dns_invalid_fields_rejected(kind,value):
    with pytest.raises(HTTPException):dns_rpc.parameters('dc.example.com',{'zone':'example.com','name':'node','type':kind,'value':value})
