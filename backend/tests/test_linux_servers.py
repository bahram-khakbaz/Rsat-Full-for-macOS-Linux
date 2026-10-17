import base64
import queue
import socket
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import issue_token
from app.db import Base, SshLinuxServer, SshSwitch, get_db
from app.main import app
from app.routers import ssh

URL = "/api/ssh/linux-servers"


def headers(user="operator", role="network"):
    return {"Authorization": "Bearer " + issue_token(user, role)}


@pytest.fixture
def inventory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = db
    monkeypatch.setattr(ssh, "SessionLocal", factory)
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    ssh._tickets.clear()
    engine.dispose()


def add(client, **changes):
    value = {"name": "Linux test", "host": "192.0.2.8", "username": "operator",
             "password": "test-only-secret", **changes}
    response = client.post(URL, headers=headers(), json=value)
    assert response.status_code == 200
    return response.json()


def test_inventory_crud_owner_and_switch_isolation(inventory):
    client, factory = inventory
    row = add(client)
    assert "password" not in row and row["password_configured"]
    assert client.get(URL, headers=headers("someone-else")).json() == []
    assert client.get("/api/ssh/switches", headers=headers()).json() == []
    with factory() as db:
        stored = db.get(SshLinuxServer, row["id"])
        assert stored.password.startswith("enc:")
        assert stored.password != "test-only-secret"
        assert db.query(SshSwitch).count() == 0
    assert client.delete(URL+f'/{row["id"]}', headers=headers("someone-else")).status_code == 404
    updated = client.put(URL+f'/{row["id"]}', headers=headers(), json={
        "name":"Renamed", "host":row["host"], "username":"new-user", "password":""})
    assert updated.json()["password_configured"]
    assert updated.json()["username"] == "new-user"
    assert client.delete(URL+f'/{row["id"]}', headers=headers()).status_code == 200
    assert client.get(URL, headers=headers()).json() == []


def test_rbac_and_input_validation(inventory):
    client, _ = inventory
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=headers(role="read_only")).status_code == 403
    assert client.post(URL, headers=headers(role="helpdesk"), json={
        "name":"test", "host":"192.0.2.1"}).status_code == 403
    assert client.post(URL, headers=headers(), json={
        "name":"test", "host":"https://bad.example/path", "password":"secret"}).status_code == 422
    assert client.post(URL, headers=headers(), json={
        "name":"test", "host":"192.0.2.1", "port":70000}).status_code == 422


def test_trust_and_destination_change_before_credentials(inventory, monkeypatch):
    client, factory = inventory
    row=add(client); path=URL+f'/{row["id"]}'
    assert client.post(path+"/ticket", headers=headers()).status_code == 409
    key="SHA256:"+"A"*43
    monkeypatch.setattr(ssh,"inspect",lambda host,port:dict(fingerprint=key,algorithm="ssh-ed25519",host=host,port=port))
    assert client.post(path+"/inspect",headers=headers()).json()["fingerprint"] == key
    assert client.post(path+"/trust",headers=headers(),json={"fingerprint":"SHA256:"+"B"*43}).status_code == 409
    assert client.post(path+"/trust",headers=headers(),json={"fingerprint":key}).status_code == 200
    ticket=client.post(path+"/ticket",headers=headers()).json()["ticket"]
    with pytest.raises(HTTPException):ssh.consume_ticket(ticket,row["id"])
    # A matching numerical ID in the switch inventory cannot consume a Linux ticket.
    ticket=client.post(path+"/ticket",headers=headers()).json()["ticket"]
    assert ssh.consume_ticket(ticket,row["id"],scope="linux").username == "operator"
    changed={"name":"test","host":"192.0.2.9","username":"operator"}
    assert client.put(path,headers=headers(),json=changed).status_code == 422
    changed["password"]="test-only-new-secret"
    assert client.put(path,headers=headers(),json=changed).json()["fingerprint"] == ""


def test_linux_websocket_uses_linux_inventory_and_shared_terminal(inventory, monkeypatch):
    client, factory = inventory
    row=add(client)
    with factory() as db:
        db.get(SshLinuxServer,row["id"]).fingerprint="SHA256:test"
        # Same ID in the other inventory must never select its host or account.
        db.add(SshSwitch(id=row["id"],owner="operator",name="Switch",host="192.0.2.99",
                         port=22,username="switch-user",password="",fingerprint=""))
        db.commit()
    outputs=queue.Queue();outputs.put(b"linux$ ")
    channel=Mock(closed=False)
    def recv(_):
        try:return outputs.get(timeout=.05)
        except queue.Empty:raise socket.timeout
    channel.recv=recv
    channel.sendall.side_effect=lambda value:outputs.put(b"echo: "+value)
    channel.close.side_effect=lambda:setattr(channel,"closed",True)
    transport=Mock()
    def open_shell(value):
        assert value["host"] == "192.0.2.8"
        assert value["username"] == "operator"
        return transport,channel
    monkeypatch.setattr(ssh,"open_shell",open_shell)
    token=client.post(URL+f'/{row["id"]}/ticket',headers=headers()).json()["ticket"]
    with client.websocket_connect(URL+f'/{row["id"]}/terminal') as ws:
        ws.send_json({"ticket":token})
        assert ws.receive_json() == {"type":"ready"}
        assert base64.b64decode(ws.receive_json()["data"]) == b"linux$ "
        ws.send_json({"type":"input","data":"uname\r"})
        assert base64.b64decode(ws.receive_json()["data"]) == b"echo: uname\r"
        ws.send_json({"type":"resize","cols":120,"rows":40})
        ws.send_json({"type":"disconnect"})
    assert channel.closed
    transport.close.assert_called_once()


def test_switch_ticket_cannot_enter_linux_terminal(inventory,monkeypatch):
    client,_=inventory
    from app.auth import Principal
    import time
    ssh._tickets["test-switch"]={"identity":1,"principal":Principal(username="operator",role="network"),
                                "expires":time.monotonic()+30,"scope":"switch"}
    shell=Mock();monkeypatch.setattr(ssh,"open_shell",shell)
    with client.websocket_connect(URL+"/1/terminal") as ws:
        ws.send_json({"ticket":"test-switch"})
        assert ws.receive_json()["type"] == "error"
    shell.assert_not_called()
