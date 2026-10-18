from datetime import datetime, timedelta, timezone
import json
import os
import pytest
from fastapi import HTTPException

from app.config import settings
from app.secret_store import store_credential, decrypt_secret
from app.vault_agent import namespace, reference, metadata
from test_linux_servers import inventory, headers


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "vault_credential_dir", str(tmp_path))
    monkeypatch.setattr(settings, "vault_max_age_seconds", 180)
    directory = tmp_path / namespace("operator")
    directory.mkdir(mode=0o700)
    path = directory / "linux-login.json"
    def write(password="test-only-password", age=0):
        value = {"password": password, "rendered_at": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()}
        temporary = directory / "new-delivery"
        temporary.write_text(json.dumps(value), encoding="utf-8")
        temporary.chmod(0o600)
        os.replace(temporary, path)
    write()
    return path, write


def test_reference_only_storage_rotation_and_no_local_fallback(delivery):
    path, write = delivery
    stored = store_credential("", "linux-login", "operator", previous="old-local")
    assert "test-only-password" not in stored and stored.startswith("vault-agent:v1:")
    assert metadata(stored) == {"credential_source":"vault-agent", "vault_key":"linux-login"}
    assert decrypt_secret(stored) == "test-only-password"
    write("rotated-test-password")
    assert decrypt_secret(stored) == "rotated-test-password"
    path.unlink()
    with pytest.raises(HTTPException) as error:
        decrypt_secret(stored)
    assert error.value.status_code == 503
    assert "old-local" not in error.value.detail


@pytest.mark.parametrize("age", [181, -60])
def test_stale_and_future_delivery_rejected(delivery, age):
    _, write = delivery
    write(age=age)
    with pytest.raises(HTTPException):
        decrypt_secret(reference("operator", "linux-login"))


def test_permissions_symlinks_and_owner_namespace(delivery, tmp_path):
    path, write = delivery
    stored = reference("operator", "linux-login")
    path.chmod(0o644)
    with pytest.raises(HTTPException): decrypt_secret(stored)
    write()
    target = path.with_name("other.json")
    path.rename(target); path.symlink_to(target)
    with pytest.raises(HTTPException): decrypt_secret(stored)
    path.unlink(); target.rename(path)
    with pytest.raises(HTTPException): decrypt_secret(reference("someone-else", "linux-login"))
    parent = path.parent
    real = tmp_path / "real-directory"
    parent.rename(real); parent.symlink_to(real, target_is_directory=True)
    with pytest.raises(HTTPException): decrypt_secret(stored)


@pytest.mark.parametrize("value", ["not-json", "[]", '{"password":"x"}', "x" * 17000])
def test_invalid_deliveries_do_not_echo_contents(delivery, value):
    path, _ = delivery
    path.write_text(value)
    with pytest.raises(HTTPException) as error:
        decrypt_secret(reference("operator", "linux-login"))
    assert error.value.status_code == 503
    assert str(path) not in error.value.detail and value not in error.value.detail


def test_local_credentials_unchanged_and_reference_validation(delivery, monkeypatch):
    assert decrypt_secret(store_credential("vault-agent:literal-password", None, "operator")) == "vault-agent:literal-password"
    for key in ["../outside", "/etc/passwd", "bad:key", "a/b"]:
        with pytest.raises(HTTPException): reference("operator", key)
    with pytest.raises(HTTPException): store_credential("password", "linux-login", "operator")
    monkeypatch.setattr(settings, "vault_credential_dir", "")
    with pytest.raises(HTTPException): reference("operator", "linux-login")


def test_inventory_api_never_returns_secret_and_preserves_reference(inventory, delivery):
    client, _ = inventory
    url = "/api/ssh/linux-servers"
    body = {"name":"Synthetic Vault server", "host":"192.0.2.8", "username":"operator", "vault_key":"linux-login"}
    response = client.post(url, headers=headers(), json=body)
    assert response.status_code == 200
    row = response.json()
    assert row["credential_source"] == "vault-agent" and row["password_configured"]
    assert "test-only-password" not in response.text and "password" not in row
    updated = client.put(url+f'/{row["id"]}', headers=headers(), json={"name":"Renamed", "host":body["host"], "username":"operator"})
    assert updated.json()["vault_key"] == "linux-login"
    assert client.get(url, headers=headers("another-operator")).json() == []
    bad = client.post(url, headers=headers(), json={**body, "password":"private-test-password"})
    assert bad.status_code == 422 and "private-test-password" not in bad.text
    changed = client.put(url+f'/{row["id"]}', headers=headers(), json={**body, "vault_key":"", "password":"replacement-test-password"})
    assert changed.json()["credential_source"] == "local"


def test_ad_reference_used_at_runtime_but_settings_remain_readable_on_outage(inventory, delivery, monkeypatch):
    from app import native_ad
    client, factory = inventory
    path, _ = delivery
    monkeypatch.setattr(native_ad, "SessionLocal", factory)
    response = client.put("/api/settings/native", headers=headers(role="admin"), json={
        "domain":"example.com", "username":"operator@example.com", "vault_key":"linux-login"})
    assert response.status_code == 200
    assert native_ad.configuration()["password"] == "test-only-password"
    path.unlink()
    public = client.get("/api/settings", headers=headers(role="admin"))
    assert public.status_code == 200
    assert public.json()["native"]["credential_source"] == "vault-agent"
    assert "test-only-password" not in public.text
    with pytest.raises(HTTPException): native_ad.configuration()
