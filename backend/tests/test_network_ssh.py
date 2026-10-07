import base64
import json
import struct
import time
from unittest.mock import Mock
import paramiko
import pytest
from fastapi import HTTPException
from app.native_dns import decode_record,counted_name
from app.native_network import build_script
from app.routers import ssh
from app.secret_store import encrypt_secret,decrypt_secret
from app.db import SshSwitch
from app.auth import Principal


def test_dns_ad_record_endianness_and_targets():
    def record(kind,data,ttl=3600):
        return struct.pack('<HHBBHI',len(data),kind,5,240,0,7)+struct.pack('>I',ttl)+bytes(8)+data
    assert decode_record(record(1,bytes([192,0,2,7])))=={'type':'A','value':'192.0.2.7','ttl':3600}
    name=bytes([14,2,6])+b'switch'+bytes([5])+b'local'+bytes([0])
    assert counted_name(name)=='switch.local.'
    assert decode_record(record(5,name))['value']=='switch.local.'
    srv=struct.pack('>HHH',1,2,389)+name
    assert decode_record(record(33,srv))['value']=='1 2 389 switch.local.'
    with pytest.raises(ValueError):decode_record(record(1,bytes([192,0,2,7]))[:-1])
    with pytest.raises(ValueError):counted_name(name[:-1])


def test_network_scripts_allowlist_and_injection_is_data():
    value="x'; Remove-Item C:\\ -Recurse; #"
    script=build_script('POST','/dns/zones',{'name':value,'replication_scope':'Domain','dynamic_update':'Secure'})
    assert value not in script
    encoded=script.split("FromBase64String('")[1].split("')")[0]
    assert json.loads(base64.b64decode(encoded))['name']==value
    assert '-ErrorAction SilentlyContinue' not in build_script('GET','/dns/records',params={'zone':'example.com'})
    with pytest.raises(HTTPException):build_script('POST','/arbitrary-command',{})
    with pytest.raises(HTTPException):build_script('POST','/dns/zones',{'name;bad':'x'})


def test_ssh_ticket_one_use_scope_and_expiry():
    p=Principal(username='owner',role='network')
    ssh._tickets['valid']={'identity':1,'principal':p,'expires':time.monotonic()+10}
    assert ssh.consume_ticket('valid',1)==p
    with pytest.raises(HTTPException):ssh.consume_ticket('valid',1)
    ssh._tickets['other']={'identity':2,'principal':p,'expires':time.monotonic()+10}
    with pytest.raises(HTTPException):ssh.consume_ticket('other',1)
    ssh._tickets['expired']={'identity':1,'principal':p,'expires':time.monotonic()-1}
    with pytest.raises(HTTPException):ssh.consume_ticket('expired',1)


def test_ssh_host_key_blocks_before_password(monkeypatch):
    t=Mock();t.get_remote_server_key.return_value=paramiko.RSAKey.generate(1024)
    monkeypatch.setattr(ssh,'transport',lambda *args:t)
    row={'host':'switch.example.com','port':22,'username':'operator','password':encrypt_secret('test-secret'),'fingerprint':'SHA256:wrong'}
    with pytest.raises(HTTPException,match='409'):ssh.open_shell(row)
    t.auth_password.assert_not_called();t.close.assert_called_once()
    row['fingerprint']=ssh.fingerprint(t.get_remote_server_key.return_value)
    ssh.open_shell(row)
    t.auth_password.assert_called_once_with('operator','test-secret',fallback=False)


def test_inventory_never_returns_password():
    secret=encrypt_secret('test-secret')
    row=SshSwitch(id=1,owner='owner',name='switch',host='192.0.2.1',port=22,username='operator',password=secret,fingerprint='')
    assert secret.startswith('enc:') and decrypt_secret(secret)=='test-secret'
    assert ssh.public(row)['password_configured'] is True
    assert 'password' not in ssh.public(row) and 'test-secret' not in json.dumps(ssh.public(row))
    with pytest.raises(ValueError):ssh.SwitchBody(name='x',host='https://example.com/',username='u')


def test_ssh_interactive_pty_round_trip():
    import socket
    import threading
    from concurrent.futures import ThreadPoolExecutor
    host_key=paramiko.RSAKey.generate(2048)
    shell_ready=threading.Event()
    class Server(paramiko.ServerInterface):
        def check_auth_password(self,username,password):
            return paramiko.AUTH_SUCCESSFUL if (username,password)==('operator','test-secret') else paramiko.AUTH_FAILED
        def get_allowed_auths(self,username):return 'password'
        def check_channel_request(self,kind,chanid):return paramiko.OPEN_SUCCEEDED if kind=='session' else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        def check_channel_pty_request(self,*args):return True
        def check_channel_shell_request(self,channel):shell_ready.set();return True
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(5)
    port=listener.getsockname()[1]
    def serve():
        sock,_=listener.accept();t=paramiko.Transport(sock);t.add_server_key(host_key)
        try:
            t.start_server(server=Server());channel=t.accept(5)
            assert channel and shell_ready.wait(5)
            channel.sendall(b'Switch> ')
            assert channel.recv(100)==b'show test\r'
            channel.sendall(b'OK\r\nSwitch> ')
            threading.Event().wait(.1)
        finally:t.close();listener.close()
    with ThreadPoolExecutor(1) as pool:
        future=pool.submit(serve)
        t,channel=ssh.open_shell({'host':'127.0.0.1','port':port,'username':'operator','password':encrypt_secret('test-secret'),'fingerprint':ssh.fingerprint(host_key)})
        try:
            assert channel.recv(100)==b'Switch> '
            channel.sendall(b'show test\r')
            assert channel.recv(100)==b'OK\r\nSwitch> '
        finally:channel.close();t.close()
        future.result(timeout=5)


def test_terminal_websocket_ticket_and_stream(monkeypatch):
    import queue
    import socket
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from app.main import app
    outputs=queue.Queue()
    outputs.put(b'Switch> ')
    channel=Mock(closed=False)
    def recv(_):
        try:return outputs.get(timeout=.1)
        except queue.Empty:raise socket.timeout
    channel.recv=recv
    channel.sendall.side_effect=lambda value:outputs.put(b'echo: '+value)
    channel.close.side_effect=lambda:setattr(channel,'closed',True)
    context=MagicMock()
    monkeypatch.setattr(ssh,'SessionLocal',lambda:context)
    row=SshSwitch(id=1,name='test switch',owner='operator',host='192.0.2.1',port=22,username='test',password=encrypt_secret('test-secret'),fingerprint='SHA256:test')
    monkeypatch.setattr(ssh,'owned',lambda *args:row)
    monkeypatch.setattr(ssh,'open_shell',lambda row:(Mock(),channel))
    audit=[]
    monkeypatch.setattr(ssh,'write_audit',lambda db,p,action,*args,**kwargs:audit.append(action))
    ssh._tickets['test-ticket']={'identity':1,'principal':Principal(username='operator',role='network'),'expires':time.monotonic()+10}
    with TestClient(app).websocket_connect('/api/ssh/switches/1/terminal') as ws:
        ws.send_json({'ticket':'test-ticket'})
        assert ws.receive_json()=={'type':'ready'}
        assert base64.b64decode(ws.receive_json()['data'])==b'Switch> '
        ws.send_json({'type':'input','data':'show test\r'})
        assert base64.b64decode(ws.receive_json()['data'])==b'echo: show test\r'
        ws.send_json({'type':'disconnect'})
    assert 'test-ticket' not in ssh._tickets
    assert 'ssh.connect' in audit and 'ssh.disconnect' in audit
    assert channel.closed


def test_ssh_rbac_requires_connect_and_write():
    from app.auth import require,Principal
    for permission in ['ssh.read','ssh.write','ssh.connect']:
        assert require(permission)(Principal(username='n',role='network')).username=='n'
        with pytest.raises(HTTPException) as error:
            require(permission)(Principal(username='r',role='read_only'))
        assert error.value.status_code==403


def test_ssh_keyboard_interactive_only_answers_password(monkeypatch):
    t=Mock();key=paramiko.RSAKey.generate(1024);t.get_remote_server_key.return_value=key
    t.auth_password.side_effect=paramiko.BadAuthenticationType('Unsupported',['keyboard-interactive'])
    monkeypatch.setattr(ssh,'transport',lambda *args:t)
    row={'host':'192.0.2.1','port':22,'username':'operator','password':encrypt_secret('test-secret'),'fingerprint':ssh.fingerprint(key)}
    def interactive(user,answer):
        assert answer('','','Password:' and [('Password:',False)])==['test-secret']
        for prompt in [('OTP code:',False),('New password:',False),('Password:',True)]:
            with pytest.raises(HTTPException):answer('','',[prompt])
    t.auth_interactive.side_effect=interactive
    ssh.open_shell(row)


def test_ssh_ticket_requires_account_before_any_connection(monkeypatch):
    row=Mock(fingerprint='SHA256:approved',username='',password=encrypt_secret('test-only'))
    monkeypatch.setattr(ssh,'owned',lambda *args:row)
    before=len(ssh._tickets)
    with pytest.raises(HTTPException) as error:ssh.ticket(1,Principal(username='owner',role='network'),Mock())
    assert error.value.status_code==409 and 'username' in error.value.detail
    assert len(ssh._tickets)==before


def test_switch_username_update_preserves_password_and_trust(monkeypatch):
    row=Mock(host='192.0.2.1',port=22,username='old-account',password=encrypt_secret('test-only'),fingerprint='SHA256:approved')
    password=row.password
    monkeypatch.setattr(ssh,'owned',lambda *args:row)
    monkeypatch.setattr(ssh,'write_audit',lambda *args,**kwargs:None)
    monkeypatch.setattr(ssh,'public',lambda r:{'username':r.username})
    body=ssh.SwitchBody(name='switch',host='192.0.2.1',username='operator',password='')
    assert ssh.update(1,body,Principal(username='owner',role='network'),Mock())['username']=='operator'
    assert row.password==password and row.fingerprint=='SHA256:approved'
