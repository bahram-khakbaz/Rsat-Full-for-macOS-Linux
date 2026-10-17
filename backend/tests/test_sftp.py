"""Real SSH/SFTP round trips against a disposable loopback-only test server."""
import errno
import asyncio
import hashlib
import io
import os
import posixpath
import socket
import stat
import threading
import time
import zipfile
from pathlib import Path

import paramiko
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import issue_token
from app.auth import Principal
from starlette.requests import ClientDisconnect
from app.db import AuditLog, Base, SshLinuxServer, SshSwitch, get_db
from app.main import app
from app.routers import sftp, ssh
from app.secret_store import encrypt_secret


def headers(user="operator", role="network"):
    return {"Authorization": "Bearer " + issue_token(user, role)}


@pytest.fixture
def environment(tmp_path):
    root = tmp_path / "server"
    root.mkdir()
    host_key = paramiko.RSAKey.generate(2048)
    auth_attempts = []
    stop = threading.Event()
    transports, threads = [], []

    class Auth(paramiko.ServerInterface):
        def check_auth_password(self, username, password):
            auth_attempts.append(username)
            return (paramiko.AUTH_SUCCESSFUL if (username, password) ==
                    ("transfer-user", "test-only-secret") else paramiko.AUTH_FAILED)

        def get_allowed_auths(self, username):
            return "password"

        def check_channel_request(self, kind, chanid):
            return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    class Files(paramiko.SFTPServerInterface):
        def location(self, value, follow=True):
            relative = posixpath.normpath("/" + value).lstrip("/")
            path = root / relative
            check = path.resolve() if follow else path.parent.resolve()
            if not check.is_relative_to(root) and path != root:
                raise PermissionError(errno.EACCES, "outside")
            return path

        def canonicalize(self, path):
            return posixpath.normpath("/" + path)

        def list_folder(self, path):
            try:
                result = []
                for child in self.location(path).iterdir():
                    entry = paramiko.SFTPAttributes.from_stat(child.lstat())
                    entry.filename = child.name
                    result.append(entry)
                return result
            except OSError as error:
                return paramiko.SFTPServer.convert_errno(error.errno)

        def stat(self, path):
            try:
                return paramiko.SFTPAttributes.from_stat(self.location(path).stat())
            except OSError as error:
                return paramiko.SFTPServer.convert_errno(error.errno)

        def lstat(self, path):
            try:
                return paramiko.SFTPAttributes.from_stat(self.location(path, False).lstat())
            except OSError as error:
                return paramiko.SFTPServer.convert_errno(error.errno)

        def open(self, path, flags, attr):
            try:
                if path.startswith("/denied/") and flags & (os.O_WRONLY | os.O_RDWR):
                    return paramiko.SFTP_PERMISSION_DENIED
                fd = os.open(self.location(path), flags, 0o600)
                mode = "r+b" if flags & os.O_RDWR else "wb" if flags & os.O_WRONLY else "rb"
                stream = os.fdopen(fd, mode)
                handle = paramiko.SFTPHandle(flags)
                handle.readfile = handle.writefile = stream
                return handle
            except OSError as error:
                return paramiko.SFTPServer.convert_errno(error.errno)

        def operation(self, name, path, other=None):
            try:
                target = self.location(path, name not in ("remove", "rename"))
                if name == "mkdir":
                    target.mkdir()
                elif name == "rmdir":
                    target.rmdir()
                elif name == "remove":
                    target.unlink()
                elif name == "rename":
                    destination = self.location(other)
                    if destination.exists():
                        return paramiko.SFTP_FAILURE
                    target.rename(destination)
                elif name == "replace":
                    os.replace(target, self.location(other))
                return paramiko.SFTP_OK
            except OSError as error:
                return paramiko.SFTPServer.convert_errno(error.errno)

        def mkdir(self, path, attr): return self.operation("mkdir", path)
        def rmdir(self, path): return self.operation("rmdir", path)
        def remove(self, path): return self.operation("remove", path)
        def rename(self, path, other): return self.operation("rename", path, other)
        def posix_rename(self, path, other): return self.operation("replace", path, other)

        def chattr(self, path, attr):
            try:
                self.location(path).chmod(attr.st_mode)
                return paramiko.SFTP_OK
            except OSError as error:
                return paramiko.SFTPServer.convert_errno(error.errno)

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(10)
    listener.settimeout(0.1)

    def serve_client(sock):
        transport = paramiko.Transport(sock)
        transports.append(transport)
        transport.add_server_key(host_key)
        transport.set_subsystem_handler("sftp", paramiko.SFTPServer, Files)
        try:
            transport.start_server(server=Auth())
            while transport.is_active() and not stop.wait(0.02):
                pass
        except (EOFError, OSError, paramiko.SSHException):
            pass
        finally:
            transport.close()

    def serve():
        while not stop.is_set():
            try:
                sock, _ = listener.accept()
            except (socket.timeout, OSError):
                continue
            thread = threading.Thread(target=serve_client, args=(sock,), daemon=True)
            threads.append(thread)
            thread.start()

    accept_thread = threading.Thread(target=serve, daemon=True)
    accept_thread.start()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        row = SshLinuxServer(owner="operator", name="Loopback SFTP", host="127.0.0.1",
            port=listener.getsockname()[1], username="transfer-user",
            password=encrypt_secret("test-only-secret"), fingerprint=ssh.fingerprint(host_key))
        db.add(row)
        db.commit()
        identity = row.id

    def db_session():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = db_session
    try:
        with TestClient(app) as client:
            yield client, root, factory, f"/api/sftp/linux/{identity}", auth_attempts
    finally:
        app.dependency_overrides.pop(get_db, None)
        stop.set()
        listener.close()
        for transport in transports:
            transport.close()
        accept_thread.join(timeout=2)
        for thread in threads:
            thread.join(timeout=2)
        engine.dispose()


def test_binary_upload_download_list_and_audit(environment):
    client, root, factory, url, _ = environment
    content = bytes(range(256)) * 4097
    response = client.put(url + "/file", params={"path": "/فارسی binary.bin"},
                          content=content, headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()["bytes"] == len(content)
    assert response.json()["source_sha256"] == hashlib.sha256(content).hexdigest()
    assert stat.S_IMODE((root / "فارسی binary.bin").stat().st_mode) == 0o600
    result = client.get(url + "/list", headers=headers()).json()
    assert result["path"] == "/" and result["entries"][0]["size"] == len(content)
    downloaded = client.get(url + "/file", params={"path": "/فارسی binary.bin"}, headers=headers())
    assert downloaded.status_code == 200 and downloaded.content == content
    assert "filename*=UTF-8''" in downloaded.headers["content-disposition"]
    assert not list(root.glob(".rsat-upload-*"))
    with factory() as db:
        records = db.query(AuditLog).all()
        assert {r.action for r in records} == {"sftp.upload", "sftp.download"}
        assert all("test-only-secret" not in r.details for r in records)


def test_owner_rbac_and_kind_do_not_open_connection(environment):
    client, _, factory, url, attempts = environment
    assert client.get(url + "/list").status_code == 401
    assert client.get(url + "/list", headers=headers("other")).status_code == 404
    assert client.get(url + "/list", headers=headers(role="helpdesk")).status_code == 403
    assert client.put(url + "/file?path=/x", headers=headers(role="read_only"), content=b"x").status_code == 403
    assert client.get(url.replace("/linux/", "/invalid/") + "/list", headers=headers()).status_code == 422
    assert client.get(url.replace("/linux/", "/switch/") + "/list", headers=headers()).status_code == 404
    assert not attempts


def test_changed_key_blocks_before_password_and_remote_bad_login_is_not_panel_logout(environment):
    client, _, factory, url, attempts = environment
    with factory() as db:
        row = db.query(SshLinuxServer).one()
        original = row.fingerprint
        row.fingerprint = "SHA256:wrong"
        db.commit()
    assert client.get(url + "/list", headers=headers()).status_code == 409
    assert attempts == []
    with factory() as db:
        row = db.query(SshLinuxServer).one()
        row.fingerprint = original
        row.password = encrypt_secret("wrong-test-only")
        db.commit()
    response = client.get(url + "/list", headers=headers())
    assert response.status_code == 403 and "wrong-test-only" not in response.text


def test_overwrite_is_explicit_atomic_and_preserves_normal_permissions(environment):
    client, root, _, url, _ = environment
    target = root / "existing.txt"
    target.write_bytes(b"original")
    target.chmod(0o640)
    response = client.put(url + "/file?path=/existing.txt", content=b"new", headers=headers())
    assert response.status_code == 409 and target.read_bytes() == b"original"
    response = client.put(url + "/file?path=/existing.txt&overwrite=true", content=b"new", headers=headers())
    assert response.status_code == 200 and target.read_bytes() == b"new"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert not list(root.glob(".rsat-upload-*"))


def test_upload_limit_cleans_partial_and_never_replaces_destination(environment, monkeypatch):
    client, root, _, url, _ = environment
    monkeypatch.setattr(sftp, "MAX_BYTES", 3)
    (root / "keep").write_bytes(b"old")
    assert client.put(url + "/file?path=/large", content=b"large", headers=headers()).status_code == 413
    response = client.put(url + "/file?path=/keep&overwrite=true", content=iter([b"ab", b"cd"]), headers=headers())
    assert response.status_code == 413
    assert (root / "keep").read_bytes() == b"old"
    assert not list(root.glob(".rsat-upload-*"))


def test_editor_detects_changed_file_and_links_are_not_overwritten(environment):
    client, root, _, url, _ = environment
    target = root / "edit"
    target.write_bytes(b"old")
    response = client.put(url + "/file", params={"path":"/edit", "overwrite":True,
        "expected_mtime":int(target.stat().st_mtime)-5,"expected_size":3}, content=b"changed", headers=headers())
    assert response.status_code == 409 and target.read_bytes() == b"old"
    (root / "link").symlink_to(target)
    assert client.put(url + "/file?path=/link&overwrite=true",content=b"bad",headers=headers()).status_code == 409
    assert target.read_bytes() == b"old"


def test_directory_upload_empty_file_and_file_management(environment):
    client, root, _, url, _ = environment
    response = client.put(url + "/file?path=/new/sub/empty&create_parents=true",content=b"",headers=headers())
    assert response.status_code == 200 and (root / "new/sub/empty").read_bytes() == b""
    for operation, body in [("mkdir",{"path":"/folder"}),
        ("rename",{"path":"/new/sub/empty","destination":"/folder/renamed"}),
        ("chmod",{"path":"/folder/renamed","mode":"0600"})]:
        response = client.post(url + "/" + operation,json=body,headers=headers())
        assert response.status_code == 200,response.text
    (root / "other").write_bytes(b"keep")
    assert client.post(url+"/rename",json={"path":"/folder/renamed","destination":"/other"},headers=headers()).status_code == 409
    assert client.post(url+"/delete",json={"path":"/"},headers=headers()).status_code == 422
    assert client.post(url+"/delete",json={"path":"/folder"},headers=headers()).status_code == 409
    assert client.post(url+"/delete",json={"path":"/folder/renamed"},headers=headers()).status_code == 200
    assert client.post(url+"/delete",json={"path":"/folder"},headers=headers()).status_code == 200
    assert client.get(url+"/file?path=/missing",headers=headers()).status_code == 404
    assert client.get(url+"/file?path=/new",headers=headers()).status_code == 409


def test_zip_download_keeps_hierarchy_skips_links_and_enforces_limit(environment, monkeypatch):
    client, root, _, url, _ = environment
    (root / "folder/sub").mkdir(parents=True)
    (root / "folder/sub/file.bin").write_bytes(b"\x00\xff\x01")
    (root / "folder/link").symlink_to(root.parent / "private")
    response = client.get(url+"/archive?path=/folder",headers=headers())
    assert response.status_code == 200 and response.headers["x-skipped-links"] == "1"
    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        assert bundle.read("folder/sub/file.bin") == b"\x00\xff\x01"
        assert all("link" not in name for name in bundle.namelist())
    monkeypatch.setattr(sftp,"MAX_BYTES",2)
    assert client.get(url+"/archive?path=/folder",headers=headers()).status_code == 413


def test_cancelled_upload_keeps_old_file_and_removes_partial(environment):
    _, root, factory, _, _ = environment
    (root / "keep").write_bytes(b"original")

    class Disconnected:
        headers = {}

        async def stream(self):
            yield b"partial"
            raise ClientDisconnect()

    with factory() as db:
        with pytest.raises(ClientDisconnect):
            asyncio.run(sftp.upload("linux", 1, Disconnected(), "/keep", overwrite=True,
                create_parents=False, expected_mtime=None, expected_size=None,
                p=Principal(username="operator", role="network"), db=db))
    assert (root / "keep").read_bytes() == b"original"
    assert not list(root.glob(".rsat-upload-*"))


def test_remote_write_permission_error_is_clear_without_logging_out(environment):
    client, root, _, url, _ = environment
    (root / "denied").mkdir()
    response = client.put(url+"/file?path=/denied/file",content=b"sample",headers=headers())
    assert response.status_code == 403
    assert "cannot write" in response.json()["detail"]
    assert not list((root / "denied").iterdir())
