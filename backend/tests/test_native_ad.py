import ssl
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from ldap3 import Connection, Server, MOCK_SYNC, MODIFY_REPLACE
from app import native_ad as n
from app.routers.settings import NativeBody, validate_native

BASE='DC=example,DC=com'
DN='CN=Test User,OU=People,'+BASE

@pytest.fixture
def directory():
    d=n.Directory({'domain':'example.com','username':'test@example.com','password':'secret','hosts':['dc.example.com']})
    d.conn=Connection(Server('mock'),client_strategy=MOCK_SYNC)
    d.conn.bind()
    d.host='dc.example.com'
    d.conn.strategy.add_entry(BASE,{'objectClass':['top','domain'],'name':'example'})
    d.conn.strategy.add_entry('OU=People,'+BASE,{'objectClass':['top','organizationalUnit'],'name':'People'})
    d.conn.strategy.add_entry(DN,{'objectClass':['top','person','user'],'objectCategory':'person','sAMAccountName':'tester','name':'Test User','displayName':'Test User','userAccountControl':66048,'msDS-User-Account-Control-Computed':16,'mail':'test@example.com'})
    return d

def test_real_mock_ldap_reads_and_escaped_search(directory):
    users=directory.request('GET','/ad/users')
    assert len(users)==1 and users[0]['samAccountName']=='tester'
    assert users[0]['enabled'] and users[0]['lockedOut'] and users[0]['passwordNeverExpires']
    assert len(directory.request('GET','/ad/users',params={'q':'Test'}))==1
    # ldap3's mock server reconstructs filters without escaping; validate the actual
    # outbound filter before that mock-only reparse.
    captured=[]
    directory.search=lambda base,filter,attrs:captured.append(filter) or []
    assert directory.request('GET','/ad/users',params={'q':'*)(objectClass=*)'})==[]
    assert r'\2a\29\28objectClass=\2a\29' in captured[0]
    from ldap3.operation.search import parse_filter
    parse_filter(captured[0],None,True,False,None,False)

def test_contact_numbers_preserve_distinct_ad_attributes(directory):
    contacts = {"mobile":["+1 555 0100"], "otherMobile":["+1 555 0101", "+1 555 0102"],
                "telephoneNumber":["1234"], "homePhone":["+1 555 0103"], "ipPhone":["5678"]}
    directory.conn.modify(DN, {key:[(MODIFY_REPLACE, value)] for key,value in contacts.items()})
    detail = directory.request('GET','/ad/users/tester')
    for key,value in contacts.items():
        assert detail[key] == (value if key == 'otherMobile' else value[0])
    # A secondary mobile must still be returned when the primary field is absent.
    directory.conn.modify(DN, {'mobile':[(MODIFY_REPLACE, [])]})
    detail = directory.request('GET','/ad/users/tester')
    assert detail['mobile'] == ''
    assert detail['otherMobile'] == contacts['otherMobile']
    directory.request('PATCH','/ad/users/tester', {'mobile':'+1 555 0104'})
    assert directory.request('GET','/ad/users/tester')['otherMobile'] == contacts['otherMobile']

def test_missing_contact_numbers_are_empty(directory):
    detail = directory.request('GET','/ad/users/tester')
    assert detail['otherMobile'] == []
    assert all(detail[key] == '' for key in ('mobile','telephoneNumber','homePhone','ipPhone'))

def test_disable_enable_preserves_other_uac_flags(directory):
    directory.request('POST','/ad/users/tester/disable')
    assert not directory.request('GET','/ad/users/tester')['enabled']
    directory.request('POST','/ad/users/tester/enable')
    assert directory.find('tester','user',['userAccountControl'])['userAccountControl']==['66048']

def test_password_reset_uses_admin_reset_and_sets_next_logon_once(directory):
    directory.conn.extend.microsoft.modify_password=Mock(return_value=True)
    directory.conn.modify=Mock(return_value=True)
    result=directory.request('POST','/ad/users/tester/reset-password',
                             {'new_password':'Abcd12!x','must_change':True})
    assert result['ok']
    directory.conn.extend.microsoft.modify_password.assert_called_once_with(DN,'Abcd12!x')
    directory.conn.modify.assert_called_once_with(DN,{'pwdLastSet':[(MODIFY_REPLACE,[0])]})

def test_rejected_password_does_not_change_logon_flags(directory):
    directory.conn.extend.microsoft.modify_password=Mock(return_value=False)
    directory.conn.modify=Mock()
    directory.conn.result={'result':19,'description':'constraintViolation'}
    with pytest.raises(HTTPException):
        directory.request('POST','/ad/users/tester/reset-password',
                          {'new_password':'Abcd12!x','must_change':True})
    directory.conn.modify.assert_not_called()

def test_membership_uses_distinguished_names(directory):
    group='CN=Helpdesk,'+BASE
    directory.conn.strategy.add_entry(group,{'objectClass':['top','group'],'name':'Helpdesk','sAMAccountName':'Helpdesk','groupType':-2147483646})
    directory.request('POST','/ad/groups/Helpdesk/members',{'member':'tester'})
    row=directory.find('Helpdesk','group',['member'])
    assert row['member']==[DN]
    directory.request('DELETE','/ad/groups/Helpdesk/members/tester')
    assert not directory.find('Helpdesk','group',['member']).get('member')

def test_failed_page_does_not_return_partial_results(directory):
    directory.conn=Mock()
    def search(*args,**kwargs):
        directory.conn.response=[{'type':'searchResEntry','dn':DN,'attributes':{'name':['Test']}}]
        directory.conn.result={'result':4,'description':'sizeLimitExceeded'}
    directory.conn.search.side_effect=search
    with pytest.raises(HTTPException):directory.search(BASE,'(objectClass=*)',['name'])

def test_pagination_retrieves_all_pages(directory):
    directory.conn=Mock()
    cookies=[]
    def search(*args,**kwargs):
        cookies.append(kwargs.get('paged_cookie'))
        idx=len(cookies)
        directory.conn.response=[{'type':'searchResEntry','dn':str(idx),'attributes':{'name':[str(idx)]}}]
        directory.conn.result={'result':0,'controls':{'1.2.840.113556.1.4.319':{'value':{'cookie':b'next' if idx==1 else b''}}}}
    directory.conn.search.side_effect=search
    assert len(directory.search(BASE,'(objectClass=*)',['name']))==2
    assert cookies==[None,b'next']

def test_bad_password_is_attempted_once_not_on_every_dc(monkeypatch):
    n.reset_auth_failure()
    c=Mock();c.bind.return_value=False;c.result={'result':49}
    factory=Mock(return_value=c);monkeypatch.setattr(n,'Connection',factory)
    cfg={'domain':'example.com','username':'test@example.com','password':'wrong','hosts':['one.example.com','two.example.com']}
    for _ in range(2):
        with pytest.raises(HTTPException) as err:n.Directory(cfg).__enter__()
        assert err.value.status_code==422
    assert factory.call_count==1
    assert factory.call_args.args[0].ssl and factory.call_args.args[0].tls.validate==ssl.CERT_REQUIRED
    n.reset_auth_failure()

def test_unsupported_never_binds(monkeypatch):
    factory=Mock();monkeypatch.setattr(n,'Directory',factory)
    for path in ['/dhcp/scopes','/dns/zones','/domain/replication','/gpo/test/report']:
        with pytest.raises(HTTPException) as err:n.request('GET',path)
        assert err.value.status_code==501
    factory.assert_not_called()

def test_settings_validate_upn_host_and_ca():
    assert validate_native(NativeBody(domain='Example.com',username='test@example.com',preferred_dc='dc.example.com'))['domain']=='example.com'
    for bad in [dict(preferred_dc='dc.other.com'),dict(username='EXAMPLE\\test'),dict(ca_pem='invalid'),dict(domain='example.com/path')]:
        data={'domain':'example.com','username':'test@example.com'};data.update(bad)
        with pytest.raises(HTTPException):validate_native(NativeBody(**data))

def test_password_is_never_returned_in_public_settings():
    result=n.public_configuration({'native_config':'{"domain":"example.com","username":"test@example.com"}','native_password':'enc:secret'})
    assert result['password_configured'] and 'password' not in result and 'enc:secret' not in str(result)

def test_move_rejects_outside_domain(directory):
    with pytest.raises(HTTPException):directory.request('POST','/ad/users/tester/move',{'target_ou':'OU=Users,DC=other,DC=com'})

@pytest.fixture
def leaf_certificate():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from datetime import datetime, timedelta, timezone
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME,'dc.example.com')])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(123).not_valid_before(datetime.now(timezone.utc)-timedelta(days=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=7)).add_extension(x509.SubjectAlternativeName([x509.DNSName('dc.example.com')]),False).sign(key,hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.DER)

def test_pinned_certificate_hostname_and_fingerprint(leaf_certificate,monkeypatch):
    der=leaf_certificate
    info=n.certificate_details('dc.example.com',der)
    assert info['hostname_valid'] and info['time_valid']
    assert not n.certificate_details('other.example.com',der)['hostname_valid']
    connection=Mock();connection.socket.getpeercert.return_value=der
    monkeypatch.setattr(n.Tls,'wrap_socket',lambda *a,**kw:None)
    tls=n.PinnedTls('dc.example.com',info['fingerprint'])
    tls.wrap_socket(connection)
    connection.socket.close.assert_not_called()
    with pytest.raises(HTTPException):n.PinnedTls('dc.example.com','0'*64).wrap_socket(connection)
    connection.socket.close.assert_called_once()


def test_computer_move_route_precedes_generic_action():
    from app.routers.ad import router
    from starlette.routing import Match
    scope={"type":"http","path":"/api/ad/computers/PC-01/move","method":"POST"}
    route=next(r for r in router.routes if r.matches(scope)[0]==Match.FULL)
    assert route.endpoint.__name__=='move_computer'


def test_untrusted_certificate_reports_setup_error_without_trying_all_dcs(monkeypatch):
    from ldap3.core.exceptions import LDAPSocketOpenError
    n.reset_auth_failure()
    c=Mock();c.bind.side_effect=LDAPSocketOpenError('CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate')
    factory=Mock(return_value=c);monkeypatch.setattr(n,'Connection',factory)
    cfg={'domain':'example.com','username':'test@example.com','password':'not-printed','hosts':['one.example.com','two.example.com']}
    with pytest.raises(HTTPException) as err:n.Directory(cfg).__enter__()
    assert err.value.status_code==409 and 'not trusted' in err.value.detail
    assert 'not-printed' not in err.value.detail
    assert factory.call_count==1

def test_user_page_cursor_checks_query_and_does_not_scan_remaining_pages(directory):
    from app.secret_store import encrypt_secret
    import base64,jwt,time
    directory.conn=Mock()
    cookies=[]
    def search(*args,**kwargs):
        cookies.append(kwargs.get('paged_cookie'))
        directory.conn.response=[{'type':'searchResEntry','dn':DN,'attributes':{'sAMAccountName':['tester'],'userAccountControl':['512']}}]
        directory.conn.result={'result':0,'controls':{'1.2.840.113556.1.4.319':{'value':{'cookie':b'next' if len(cookies)==1 else b''}}}}
    directory.conn.search.side_effect=search
    first=directory.request('GET','/ad/users',params={'q':'','page_size':15})
    assert len(first['items'])==1 and first['has_more'] and first['total'] is None
    assert directory.conn.search.call_count==1
    second=directory.request('GET','/ad/users',params={'q':'','page_size':15,'cursor':first['next_cursor']})
    assert not second['has_more'] and cookies==[None,b'next']
    with pytest.raises(HTTPException) as err:
        directory.request('GET','/ad/users',params={'q':'different','page_size':15,'cursor':first['next_cursor']})
    assert err.value.status_code==409
    with pytest.raises(HTTPException):
        directory.request('GET','/ad/users',params={'q':'','page_size':15,'cursor':'not-a-valid-cursor'})
    assert directory.conn.search.call_count==2


def test_ldap_generalized_time_is_returned_as_browser_readable_iso_date():
    assert n.date('20261007102030.0Z')=='2026-10-07T10:20:30+00:00'


def test_native_user_search_uses_index_friendly_prefixes(directory):
    captured=[]
    directory.search=lambda base,filter,attrs:captured.append(filter) or []
    directory.request('GET','/ad/users',params={'q':'tester'})
    assert '(sAMAccountName=tester*)' in captured[0]
    assert '=*tester' not in captured[0]
