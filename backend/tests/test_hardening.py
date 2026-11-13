"""Credential encryption keys, worker transport, audit outcomes and schema migrations."""

import asyncio
import ssl
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app import audit, db, demo, secret_store, worker_client, worker_tls
from app.auth import Principal, issue_token
from app.config import Settings, settings
from app.main import app
from app.runtime_config import RuntimeConfig


def test_dedicated_encryption_key_reads_legacy_values_and_rotates(monkeypatch):
    monkeypatch.setattr(settings, "encryption_key", "")
    legacy = secret_store.encrypt_secret("stored-before-upgrade")
    assert not secret_store.needs_rotation(legacy)

    monkeypatch.setattr(settings, "encryption_key", "k" * 40)
    assert secret_store.decrypt_secret(legacy) == "stored-before-upgrade"
    assert secret_store.needs_rotation(legacy)
    rotated = secret_store.rotate_secret(legacy)
    assert rotated != legacy and not secret_store.needs_rotation(rotated)
    assert secret_store.rotate_secret(rotated) == rotated

    # A later key change keeps the former key readable through the previous list.
    monkeypatch.setattr(settings, "encryption_key_previous", "k" * 40)
    monkeypatch.setattr(settings, "encryption_key", "n" * 40)
    assert secret_store.decrypt_secret(rotated) == "stored-before-upgrade"
    monkeypatch.setattr(settings, "encryption_key_previous", "")
    monkeypatch.setattr(settings, "jwt_secret", "a-different-signing-secret-of-enough-length")
    assert secret_store.decrypt_secret(rotated) == ""
    assert secret_store.rotate_secret(rotated) == rotated  # unreadable values are kept


def test_production_refuses_placeholder_secrets():
    weak = Settings(jwt_secret="change-me", admin_password="change-me", encryption_key="")
    assert len(weak.placeholder_secrets()) == 2
    strong = Settings(
        jwt_secret="s" * 48,
        admin_password="a-long-admin-password",
        encryption_key="e" * 48,
        allow_insecure_worker=False,
    )
    assert strong.placeholder_secrets() == [] and strong.weak_settings() == []


def self_signed_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "worker.example.com")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def test_worker_url_and_fingerprint_validation():
    assert worker_tls.normalize_url(" https://worker.example.com:8765/ ") == (
        "https://worker.example.com:8765"
    )
    for bad in [
        "worker.example.com:8765",
        "ftp://worker.example.com",
        "https://user:pw@worker.example.com",
        "https://worker.example.com/path",
        "https://worker.example.com?x=1",
        "https://worker.example.com:notaport",
    ]:
        with pytest.raises(HTTPException):
            worker_tls.normalize_url(bad)
    digest = "ab" * 32
    spaced = worker_tls.format_fingerprint(digest).upper()
    assert spaced.count(":") == 31 and worker_tls.normalize_fingerprint(spaced) == digest
    with pytest.raises(HTTPException):
        worker_tls.normalize_fingerprint("abcd")


def test_worker_channel_requires_tls_and_pins_the_paired_certificate(monkeypatch):
    pem = self_signed_pem()
    monkeypatch.setattr(settings, "allow_insecure_worker", False)
    with pytest.raises(HTTPException) as refused:
        worker_tls.verify_option("http://worker.example.com:8765", "")
    assert refused.value.status_code == 409 and "https://" in refused.value.detail
    pinned = worker_tls.verify_option("https://worker.example.com:8765", pem)
    assert isinstance(pinned, ssl.SSLContext)
    assert pinned.verify_mode == ssl.CERT_REQUIRED and not pinned.check_hostname
    assert worker_tls.verify_option("https://worker.example.com:8765", "") is True
    assert worker_tls.mode("https://worker.example.com", pem) == "pinned"
    assert worker_tls.mode("https://worker.example.com", "") == "ca"
    assert worker_tls.mode("http://worker.example.com", "") == "insecure"
    assert worker_tls.mode("", "") == "none"
    summary = worker_tls.certificate_summary(pem)
    assert summary["fingerprint"].count(":") == 31 and "worker.example.com" in summary["subject"]
    monkeypatch.setattr(settings, "allow_insecure_worker", True)
    assert worker_tls.verify_option("http://worker.example.com:8765", "") is True


def test_worker_requests_omit_empty_parameters_and_never_use_plain_http(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, **kwargs):
            seen.update(method=method, url=url, **kwargs)
            return httpx.Response(200, json={"items": []})

    monkeypatch.setattr(worker_client.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(settings, "allow_insecure_worker", False)
    client = worker_client.WorkerClient()
    runtime = RuntimeConfig(
        demo_mode=False, worker_url="https://worker.example.com:8765", worker_token="synthetic"
    )
    result = asyncio.run(
        client.call(
            "GET",
            "/ad/users",
            params={"q": "", "page_size": None, "cursor": "", "zone": "example.com"},
            runtime=runtime,
        )
    )
    assert result == {"items": []}
    assert seen["params"] == {"zone": "example.com"}
    assert seen["headers"] == {"Authorization": "Bearer synthetic"}
    assert seen["client"]["verify"] is True

    seen.clear()
    insecure = RuntimeConfig(
        demo_mode=False, worker_url="http://worker.example.com:8765", worker_token="synthetic"
    )
    with pytest.raises(HTTPException) as refused:
        asyncio.run(client.call("GET", "/admin/ping", runtime=insecure))
    assert refused.value.status_code == 409 and seen == {}
    unpaired = RuntimeConfig(
        demo_mode=False, worker_url="https://worker.example.com:8765", worker_token=""
    )
    with pytest.raises(HTTPException) as missing:
        asyncio.run(client.call("GET", "/admin/ping", runtime=unpaired))
    assert missing.value.status_code == 409 and seen == {}


def test_audited_records_failures_and_demo_results():
    principal = Principal(username="operator", role="admin")
    write = Mock()

    async def denied():
        raise HTTPException(403, "AD operation failed (LDAP code 50)")

    with pytest.raises(HTTPException):
        asyncio.run(audit.audited(denied, write, None, principal, "ad.user.delete", "tester"))
    assert write.call_args.kwargs["status"] == "failed"
    assert write.call_args.kwargs["details"] == {
        "error": "AD operation failed (LDAP code 50)",
        "http_status": 403,
    }

    async def simulated():
        return {"ok": True, "demo": True}

    asyncio.run(audit.audited(simulated, write, None, principal, "ad.user.delete", "tester"))
    assert write.call_args.kwargs["status"] == "demo"

    async def real():
        return {"ok": True, "dc": "dc.example.com"}

    asyncio.run(audit.audited(real, write, None, principal, "ad.user.delete", "tester"))
    assert write.call_args.kwargs["status"] == "success"


def test_failed_directory_write_is_audited_and_identity_cannot_alter_the_route(monkeypatch):
    from app.routers import ad

    request = AsyncMock(side_effect=HTTPException(403, "denied by directory"))
    recorded = Mock()
    monkeypatch.setattr(ad.worker, "request", request)
    monkeypatch.setattr(ad, "write_audit", recorded)
    headers = {"Authorization": "Bearer " + issue_token("operator", "admin")}
    response = TestClient(app).post("/api/ad/users/x%20y%3Fz%23w/unlock", headers=headers)
    assert response.status_code == 403
    request.assert_awaited_once_with("POST", "/ad/users/x%20y%3Fz%23w/unlock", payload=None)
    assert recorded.call_args.args[2:4] == ("ad.user.unlock", "x y?z#w")
    assert recorded.call_args.kwargs["status"] == "failed"
    assert recorded.call_args.kwargs["details"]["http_status"] == 403


def test_demo_user_listing_pages_without_dropping_rows():
    client = worker_client.WorkerClient()
    collected, cursor = [], ""
    while True:
        page = client._demo("GET", "/ad/users", None, {"q": "", "page_size": 2, "cursor": cursor})
        assert len(page["items"]) <= 2 and page["total"] == len(demo.USERS)
        collected += page["items"]
        if not page["has_more"]:
            assert page["next_cursor"] is None
            break
        cursor = page["next_cursor"]
    assert collected == demo.USERS
    assert client._demo("GET", "/ad/users", None, {"q": ""}) == demo.USERS
    members = client._demo("GET", "/ad/groups/IT-Admins/members", None, None)
    assert members == demo.GROUP_MEMBERS["IT-Admins"]
    assert client._demo("POST", "/ad/users/tester/unlock", None, None) == {
        "ok": True,
        "demo": True,
    }


def test_migrations_build_the_model_schema_and_adopt_an_existing_database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        # A table created by an installation that predates migrations.
        connection.execute(
            text(
                "CREATE TABLE system_settings (id INTEGER PRIMARY KEY, "
                "key VARCHAR(120) NOT NULL, value TEXT NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO system_settings (key, value) VALUES ('demo_mode', 'false')")
        )
    monkeypatch.setattr(db, "engine", engine)
    db.init_db()
    db.init_db()  # Idempotent: every start-up runs it.
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert set(db.Base.metadata.tables) | {"alembic_version"} == tables
    for name, table in db.Base.metadata.tables.items():
        migrated = {column["name"] for column in inspector.get_columns(name)}
        assert migrated == set(table.columns.keys()), name
    with engine.connect() as connection:
        value = connection.execute(text("SELECT value FROM system_settings")).scalar_one()
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert value == "false" and revision == "0002"
    engine.dispose()
