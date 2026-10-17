import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import issue_token
from app.db import Base, AuditLog, get_db
from app.main import app

URL = "/api/ipam/vlans"


def headers(user="operator", role="network"):
    return {"Authorization": "Bearer " + issue_token(user, role)}


@pytest.fixture
def inventory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    def db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = db
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def create(client, **changes):
    response = client.post(URL, headers=headers(), json={
        "name": "Synthetic VLAN", "cidr": "192.0.2.0/28", **changes})
    assert response.status_code == 200, response.text
    return response.json()


def patch(client, vlan, ip, status, **changes):
    return client.patch(f'{URL}/{vlan["id"]}/addresses/{ip}', headers=headers(), json={
        "status": status, "revision": vlan["revision"], **changes})


def test_counts_boundaries_and_persisted_status(inventory):
    client, factory = inventory
    vlan = create(client, default_status="free", states={
        "192.0.2.1": "reserved", "192.0.2.2": "used", "192.0.2.3": "unknown"})
    assert vlan["total"] == 14
    assert vlan["counts"] == {"free": 11, "used": 1, "reserved": 1, "unknown": 1}
    assert [a["ip"] for a in vlan["addresses"]] == [f"192.0.2.{i}" for i in range(1, 15)]
    changed = patch(client, vlan, "192.0.2.4", "used").json()
    assert changed["counts"]["free"] == 10 and changed["counts"]["used"] == 2
    restored = patch(client, changed, "192.0.2.4", "free").json()
    assert restored["counts"] == vlan["counts"]
    assert client.get(URL, headers=headers()).json()[0] == restored
    with factory() as db:
        assert db.query(AuditLog).filter_by(action="ipam.address.update").count() == 2


def test_stale_update_cannot_overwrite_another_change(inventory):
    client, _ = inventory
    vlan = create(client, default_status="free")
    assert patch(client, vlan, "192.0.2.2", "used").status_code == 200
    assert patch(client, vlan, "192.0.2.3", "used").status_code == 409
    stored = client.get(URL, headers=headers()).json()[0]
    assert stored["counts"] == {"free": 13, "used": 1, "reserved": 0, "unknown": 0}
    assert next(a for a in stored["addresses"] if a["ip"] == "192.0.2.3")["status"] == "free"


def test_owner_isolation_and_roles(inventory):
    client, _ = inventory
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=headers(role="read_only")).status_code == 403
    assert client.post(URL, headers=headers(role="helpdesk"), json={"name":"test","cidr":"192.0.2.0/28"}).status_code == 403
    vlan = create(client)
    assert client.get(URL, headers=headers("another-operator")).json() == []
    assert client.patch(f'{URL}/{vlan["id"]}/addresses/192.0.2.2', headers=headers("another-operator"),
                        json={"status":"used","revision":1}).status_code == 404


def test_cidr_normalization_overlap_and_invalid_inputs(inventory):
    client, _ = inventory
    vlan = create(client, cidr="192.0.2.8/28")
    assert vlan["cidr"] == "192.0.2.0/28"
    assert client.post(URL, headers=headers(), json={"name":"overlap","cidr":"192.0.2.0/29"}).status_code == 409
    for cidr in ["bad", "::/64", "0.0.0.0/0", "192.0.2.0/31", "192.0.2.1/32"]:
        assert client.post(URL, headers=headers(), json={"name":"invalid","cidr":cidr}).status_code == 422
    for ip in ["192.0.2.0", "192.0.2.15", "192.0.2.99", "bad"]:
        assert patch(client, vlan, ip, "used").status_code == 422
    assert patch(client, vlan, "192.0.2.2", "invalid").status_code == 422
    assert client.post(URL, headers=headers(), json={"name":"bad state","cidr":"198.51.100.0/28", "states":{"198.51.100.15":"free"}}).status_code == 422


def test_full_subnet_and_two_free_addresses(inventory):
    client, _ = inventory
    full = create(client, default_status="used")
    assert full["counts"]["free"] == 0 and full["counts"]["used"] == 14
    partial = create(client, cidr="198.51.100.0/27", default_status="used",
                     states={"198.51.100.14":"free", "198.51.100.15":"free"})
    assert partial["total"] == 30
    assert partial["counts"]["free"] == 2 and partial["counts"]["used"] == 28
