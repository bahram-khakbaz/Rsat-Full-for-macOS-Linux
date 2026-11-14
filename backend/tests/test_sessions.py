"""Sign-in, cookie sessions, revocation, throttling and operator management."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.config import settings
from app.db import AuditLog, Base, get_db
from app.main import app

ADMIN_PASSWORD = "synthetic-admin-password"
OPERATOR_PASSWORD = "synthetic-operator-pw"
SAME_ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def panel(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = db
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", ADMIN_PASSWORD)
    monkeypatch.setattr(settings, "login_max_failures", 3)
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def sign_in(client, username="admin", password=ADMIN_PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_login_sets_http_only_cookie_and_me_reports_permissions(panel):
    client, _ = panel
    assert client.get("/api/auth/me").status_code == 401
    response = sign_in(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    me = client.get("/api/auth/me").json()
    assert me == {
        "username": "admin",
        "role": "admin",
        "permissions": ["*"],
        "managed": "environment",
    }
    assert client.post("/api/auth/logout", headers=SAME_ORIGIN).json() == {"ok": True}
    assert client.get("/api/auth/me").status_code == 401


def test_non_ascii_credentials_are_rejected_not_a_server_error(panel):
    client, factory = panel
    assert sign_in(client, "ادمین", "گذرواژه").status_code == 401
    assert sign_in(client, "admin", "گذرواژهٔ اشتباه").status_code == 401
    with factory() as db:
        rows = db.query(AuditLog).filter_by(action="auth.login").all()
    assert [row.status for row in rows] == ["failed", "failed"]
    assert all("گذرواژه" not in row.details for row in rows)


def test_repeated_failures_lock_the_account_even_for_the_right_password(panel):
    client, _ = panel
    for _ in range(3):
        assert sign_in(client, password="wrong-password").status_code == 401
    locked = sign_in(client)
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) > 0
    auth.throttle.clear()
    assert sign_in(client).status_code == 200


def test_cookie_sessions_reject_cross_site_writes(panel):
    client, _ = panel
    sign_in(client)
    url = "/api/auth/revoke-sessions"
    assert client.post(url, headers={"Origin": "https://attacker.example"}).status_code == 403
    assert client.post(url).status_code == 403  # no Origin and no Fetch Metadata
    assert client.get("/api/auth/me").status_code == 200
    assert client.post(url, headers=SAME_ORIGIN).status_code == 200


def test_sign_out_everywhere_revokes_existing_admin_sessions(panel):
    client, _ = panel
    sign_in(client)
    other = TestClient(app)
    sign_in(other)
    assert other.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/revoke-sessions", headers=SAME_ORIGIN).status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    assert sign_in(other).status_code == 200
    assert other.get("/api/auth/me").status_code == 200


def test_operator_lifecycle_roles_and_immediate_revocation(panel):
    admin, _ = panel
    sign_in(admin)
    weak = admin.post(
        "/api/operators",
        headers=SAME_ORIGIN,
        json={"username": "desk.one", "password": "short", "role": "helpdesk"},
    )
    assert weak.status_code == 422 and "short" not in weak.text
    reserved = admin.post(
        "/api/operators",
        headers=SAME_ORIGIN,
        json={"username": "Admin", "password": OPERATOR_PASSWORD, "role": "helpdesk"},
    )
    assert reserved.status_code == 409
    created = admin.post(
        "/api/operators",
        headers=SAME_ORIGIN,
        json={"username": "desk.one", "password": OPERATOR_PASSWORD, "role": "helpdesk"},
    )
    assert created.status_code == 200, created.text
    row = created.json()
    assert row["role"] == "helpdesk" and "password" not in str(row).lower()
    duplicate = admin.post(
        "/api/operators",
        headers=SAME_ORIGIN,
        json={"username": "desk.one", "password": OPERATOR_PASSWORD, "role": "auditor"},
    )
    assert duplicate.status_code == 409

    operator = TestClient(app)
    assert sign_in(operator, "desk.one", OPERATOR_PASSWORD).status_code == 200
    me = operator.get("/api/auth/me").json()
    assert me["role"] == "helpdesk" and me["managed"] == "local"
    assert "ad.password" in me["permissions"] and "dns.write" not in me["permissions"]
    assert operator.get("/api/operators").status_code == 403

    # A role change applies to the session that is already open.
    url = f"/api/operators/{row['id']}"
    assert admin.patch(url, headers=SAME_ORIGIN, json={"role": "auditor"}).status_code == 200
    assert operator.get("/api/auth/me").json()["role"] == "auditor"

    # Disabling ends the session immediately and blocks new sign-ins.
    assert admin.patch(url, headers=SAME_ORIGIN, json={"disabled": True}).status_code == 200
    assert operator.get("/api/auth/me").status_code == 401
    assert sign_in(operator, "desk.one", OPERATOR_PASSWORD).status_code == 401

    assert admin.patch(url, headers=SAME_ORIGIN, json={"disabled": False}).status_code == 200
    auth.throttle.clear()
    assert sign_in(operator, "desk.one", OPERATOR_PASSWORD).status_code == 200
    assert admin.delete(url, headers=SAME_ORIGIN).json() == {"ok": True}
    assert operator.get("/api/auth/me").status_code == 401
    assert admin.get("/api/operators").json() == []


def test_operator_changes_own_password_and_keeps_only_this_session(panel):
    admin, _ = panel
    sign_in(admin)
    admin.post(
        "/api/operators",
        headers=SAME_ORIGIN,
        json={"username": "net.one", "password": OPERATOR_PASSWORD, "role": "network"},
    )
    first, second = TestClient(app), TestClient(app)
    sign_in(first, "net.one", OPERATOR_PASSWORD)
    sign_in(second, "net.one", OPERATOR_PASSWORD)
    replacement = "replacement-operator-pw"
    wrong = first.post(
        "/api/auth/password",
        headers=SAME_ORIGIN,
        json={"current_password": "not-the-password", "new_password": replacement},
    )
    assert wrong.status_code == 403
    changed = first.post(
        "/api/auth/password",
        headers=SAME_ORIGIN,
        json={"current_password": OPERATOR_PASSWORD, "new_password": replacement},
    )
    assert changed.status_code == 200
    assert first.get("/api/auth/me").status_code == 200
    assert second.get("/api/auth/me").status_code == 401
    assert sign_in(second, "net.one", OPERATOR_PASSWORD).status_code == 401
    assert sign_in(second, "net.one", replacement).status_code == 200
    # The environment-managed admin has no panel password to change.
    managed = admin.post(
        "/api/auth/password",
        headers=SAME_ORIGIN,
        json={"current_password": ADMIN_PASSWORD, "new_password": replacement},
    )
    assert managed.status_code == 409


def test_password_hash_round_trip_and_format():
    stored = auth.hash_password("pässwörd-with-ünicode")
    assert stored.startswith("scrypt$") and "pässwörd" not in stored
    assert auth.verify_password("pässwörd-with-ünicode", stored)
    assert not auth.verify_password("pässwörd-with-unicode", stored)
    assert not auth.verify_password("anything", "not-a-valid-hash")
