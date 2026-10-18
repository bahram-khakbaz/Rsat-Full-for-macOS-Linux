"""Authenticated SFTP file operations; no shell commands or host filesystem API."""
import errno
import hashlib
import posixpath
import secrets
import stat
import tempfile
import time
import zipfile
import anyio
from contextlib import contextmanager
from typing import Literal
from urllib.parse import quote

import paramiko
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from ..audit import write_audit
from ..auth import Principal, require
from ..db import SshLinuxServer, SshSwitch, get_db
from ..secret_store import decrypt_secret
from . import ssh

router = APIRouter(prefix="/api/sftp", tags=["file-transfer"])
Kind = Literal["linux", "switch"]
MAX_BYTES = 512 * 1024 * 1024
CHUNK = 64 * 1024


def path_value(value):
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        raise HTTPException(422, "Enter a valid remote path")
    return posixpath.normpath(value)


def owned(db, kind, identity, principal):
    return ssh.owned(db, identity, principal,
                     SshLinuxServer if kind == "linux" else SshSwitch)


def require_login(row):
    if not row.fingerprint:
        raise HTTPException(409, "Verify and approve this host key in SSH / Linux Servers first")
    if not row.username.strip() or not row.password:
        raise HTTPException(409, "Save this server's SSH username and password first")


@contextmanager
def connection(row):
    require_login(row)
    transport = client = None
    try:
        transport = ssh.transport(row.host, row.port)
        if not secrets.compare_digest(
            ssh.fingerprint(transport.get_remote_server_key()), row.fingerprint,
        ):
            raise HTTPException(409, "SSH host key changed. No password was sent. Verify it again.")
        password = decrypt_secret(row.password)
        if not password:
            raise HTTPException(409, "The saved SSH credential is unavailable")
        transport.auth_password(row.username, password, fallback=False)
        client = paramiko.SFTPClient.from_transport(transport)
        client.get_channel().settimeout(30)
        yield client
    except HTTPException:
        raise
    except paramiko.AuthenticationException as error:
        raise HTTPException(403, "The server rejected the saved SSH login") from error
    except OSError as error:
        if error.errno == errno.ENOENT:
            raise HTTPException(404, "Remote file or directory was not found") from error
        if error.errno in (errno.EACCES, errno.EPERM):
            raise HTTPException(403, "The SSH account cannot perform this file operation") from error
        if error.errno in (errno.EEXIST, errno.ENOTEMPTY):
            raise HTTPException(409, "Destination exists or directory is not empty") from error
        raise HTTPException(502, "SFTP operation failed. Check the connection and server permissions.") from error
    except (paramiko.SSHException, EOFError) as error:
        raise HTTPException(502, "SFTP is unavailable or the connection was interrupted") from error
    finally:
        if client:
            client.close()
        if transport:
            transport.close()


def metadata(entry):
    mode = entry.st_mode or 0
    return {"name": entry.filename, "type": "directory" if stat.S_ISDIR(mode)
            else "link" if stat.S_ISLNK(mode) else "file" if stat.S_ISREG(mode) else "other",
            "size": max(0, entry.st_size or 0), "modified": entry.st_mtime or 0,
            "permissions": stat.filemode(mode), "mode": format(stat.S_IMODE(mode), "04o")}


@router.get("/{kind}/{identity}/list")
def listing(kind: Kind, identity: int, path: str = ".",
            p: Principal = Depends(require("sftp.read")), db: Session = Depends(get_db)):
    row = owned(db, kind, identity, p)
    with connection(row) as client:
        canonical = client.normalize(path_value(path))
        entries, truncated = [], False
        for entry in client.listdir_iter(canonical, read_aheads=1):
            if entry.filename in (".", "..") or "/" in entry.filename or "\x00" in entry.filename:
                continue
            if len(entries) >= 10000:
                truncated = True
                break
            entries.append(metadata(entry))
        entries.sort(key=lambda value: (value["type"] != "directory", value["name"].casefold()))
        return {"path": canonical, "parent": posixpath.dirname(canonical) or "/",
                "entries": entries, "truncated": truncated, "max_file_bytes": MAX_BYTES}


def existing(client, path):
    try:
        return client.lstat(path)
    except OSError as error:
        if error.errno == errno.ENOENT:
            return None
        raise


def check_destination(client, path, overwrite, expected_mtime, expected_size):
    found = existing(client, path)
    if found and not stat.S_ISREG(found.st_mode):
        raise HTTPException(409, "Destination is not a regular file; links and directories are not overwritten")
    if found and not overwrite:
        raise HTTPException(409, "File already exists. Choose Overwrite explicitly or use a new name.")
    if expected_mtime is not None or expected_size is not None:
        if (not found or found.st_mtime != expected_mtime or found.st_size != expected_size):
            raise HTTPException(409, "Remote file changed. Reload it before saving.")
    return found


def ensure_parents(client, path):
    parts = path.split("/")
    if len(parts) > 40:
        raise HTTPException(422, "Directory nesting exceeds the transfer limit")
    current = "/" if path.startswith("/") else "."
    for part in parts:
        if not part or part == ".":
            continue
        current = posixpath.join(current, part)
        entry = existing(client, current)
        if entry is None:
            client.mkdir(current)
        elif not stat.S_ISDIR(entry.st_mode):
            raise HTTPException(409, "Upload directory contains a file or symbolic link")


@router.put("/{kind}/{identity}/file")
async def upload(kind: Kind, identity: int, request: Request, path: str,
                 overwrite: bool = False, create_parents: bool = False,
                 expected_mtime: int | None = Query(default=None, ge=0),
                 expected_size: int | None = Query(default=None, ge=0),
                 p: Principal = Depends(require("sftp.write")), db: Session = Depends(get_db)):
    row = owned(db, kind, identity, p)
    destination = path_value(path)
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if not 0 <= int(length) <= MAX_BYTES:
                raise ValueError
        except ValueError:
            raise HTTPException(413, "Maximum file size is 512 MiB") from None
    manager = connection(row)
    client = await run_in_threadpool(manager.__enter__)
    temporary = posixpath.join(posixpath.dirname(destination),
                               ".rsat-upload-" + secrets.token_hex(16) + ".part")
    handle, committed, count = None, False, 0
    digest = hashlib.sha256()
    try:
        if create_parents:
            await run_in_threadpool(ensure_parents, client, posixpath.dirname(destination))
        await run_in_threadpool(check_destination, client, destination, overwrite,
                                expected_mtime, expected_size)
        handle = await run_in_threadpool(client.open, temporary, "wx")
        await run_in_threadpool(client.chmod, temporary, 0o600)
        async for chunk in request.stream():
            count += len(chunk)
            if count > MAX_BYTES:
                raise HTTPException(413, "Maximum file size is 512 MiB")
            digest.update(chunk)
            for offset in range(0, len(chunk), CHUNK):
                await run_in_threadpool(handle.write, chunk[offset:offset + CHUNK])
        await run_in_threadpool(handle.close)
        handle = None
        if length is not None and count != int(length):
            raise HTTPException(400, "Upload was incomplete; destination was not replaced")
        if (await run_in_threadpool(client.stat, temporary)).st_size != count:
            raise HTTPException(502, "Remote size verification failed")
        prior = await run_in_threadpool(check_destination, client, destination, overwrite,
                                       expected_mtime, expected_size)
        if prior:
            # Preserve ordinary permissions of an edited/replaced file. Never
            # copy setuid/setgid bits to freshly supplied content.
            await run_in_threadpool(client.chmod, temporary, stat.S_IMODE(prior.st_mode) & 0o777)
            try:
                await run_in_threadpool(client.posix_rename, temporary, destination)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EPERM):
                    raise
                raise HTTPException(409, "Atomic overwrite failed or is unsupported; existing file was not removed. Upload under a new name.") from error
        else:
            await run_in_threadpool(client.rename, temporary, destination)
        committed = True
        write_audit(db, p, "sftp.upload", row.host,
                    details={"path": destination, "bytes": count, "overwrite": bool(prior)})
        return {"ok": True, "path": destination, "bytes": count,
                "source_sha256": digest.hexdigest(), "remote_size_verified": True}
    except (OSError, paramiko.SSHException, EOFError) as error:
        # Do not expose passwords, server banners or raw exceptions.
        if getattr(error, "errno", None) in (errno.EACCES, errno.EPERM):
            raise HTTPException(403, "The SSH account cannot write this destination") from error
        if getattr(error, "errno", None) == errno.ENOENT:
            raise HTTPException(404, "Remote upload directory was not found") from error
        raise HTTPException(502, "SFTP upload failed; incomplete upload was not committed") from error
    finally:
        with anyio.CancelScope(shield=True):
            if handle:
                try:
                    await run_in_threadpool(handle.close)
                except Exception:
                    pass
            if not committed:
                try:
                    await run_in_threadpool(client.remove, temporary)
                except Exception:
                    pass
            await run_in_threadpool(manager.__exit__, None, None, None)


@router.get("/{kind}/{identity}/file")
def download(kind: Kind, identity: int, path: str,
             p: Principal = Depends(require("sftp.read")), db: Session = Depends(get_db)):
    row = owned(db, kind, identity, p)
    remote = path_value(path)
    manager = connection(row)
    client = manager.__enter__()
    handle = None
    try:
        attributes = client.stat(remote)
        if not stat.S_ISREG(attributes.st_mode):
            raise HTTPException(409, "Select a regular file to download")
        if attributes.st_size > MAX_BYTES:
            raise HTTPException(413, "Maximum file size is 512 MiB")
        handle = client.open(remote, "rb")
    except BaseException:
        manager.__exit__(*__import__("sys").exc_info())
        raise

    closed = False

    def close():
        nonlocal closed
        if not closed:
            closed = True
            try:
                handle.close()
            finally:
                manager.__exit__(None, None, None)

    def chunks():
        count = 0
        try:
            while True:
                chunk = handle.read(CHUNK)
                if not chunk:
                    break
                count += len(chunk)
                if count > MAX_BYTES:
                    raise OSError("Download size limit exceeded")
                yield chunk
        finally:
            close()

    try:
        write_audit(db, p, "sftp.download", row.host, status="requested",
                    details={"path": remote, "bytes": attributes.st_size})
    except BaseException:
        close()
        raise
    filename = quote(posixpath.basename(remote), safe="")
    return StreamingResponse(chunks(), media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''" + filename,
                 "Content-Length": str(attributes.st_size), "X-Content-Type-Options": "nosniff"},
        background=BackgroundTask(close))


@router.get("/{kind}/{identity}/archive")
def archive(kind: Kind, identity: int, path: str,
            p: Principal = Depends(require("sftp.read")), db: Session = Depends(get_db)):
    row = owned(db, kind, identity, p)
    remote = path_value(path)
    output = tempfile.TemporaryFile()
    skipped, total, entries = 0, 0, 0
    deadline = time.monotonic() + 180
    try:
        with connection(row) as client, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
            if not stat.S_ISDIR(client.lstat(remote).st_mode):
                raise HTTPException(409, "Select an ordinary directory to download as ZIP")

            def walk(directory, prefix, depth):
                nonlocal skipped, total, entries
                if depth > 32:
                    raise HTTPException(413, "Archive nesting exceeds 32 directories")
                bundle.writestr(prefix + "/", b"")
                # Nested reads must not interleave with pipelined READDIR
                # responses on the same SFTP channel.
                for entry in client.listdir_iter(directory, read_aheads=1):
                    entries += 1
                    if entries > 10000 or time.monotonic() > deadline:
                        raise HTTPException(413, "Archive exceeds file-count or preparation-time limit")
                    name = entry.filename
                    if name in (".", "..") or any(c in name for c in ("/", "\\", "\x00")):
                        raise HTTPException(422, "Server returned an unsafe archive filename")
                    source, target = posixpath.join(directory, name), prefix + "/" + name
                    if stat.S_ISDIR(entry.st_mode):
                        walk(source, target, depth + 1)
                    elif stat.S_ISREG(entry.st_mode):
                        with client.open(source, "rb") as incoming, bundle.open(target, "w") as outgoing:
                            while True:
                                chunk = incoming.read(CHUNK)
                                if not chunk:
                                    break
                                total += len(chunk)
                                if total > MAX_BYTES or time.monotonic() > deadline:
                                    raise HTTPException(413, "Archive exceeds 512 MiB or preparation-time limit")
                                outgoing.write(chunk)
                    else:
                        skipped += 1  # No symlinks, devices, pipes or external traversal.

            root_name = posixpath.basename(remote.rstrip("/")) or "remote"
            if root_name in (".", "..") or "\\" in root_name:
                root_name = "remote"
            walk(remote, root_name, 0)
        size = output.tell()
        output.seek(0)
        write_audit(db, p, "sftp.archive", row.host,
                    details={"path": remote, "bytes": total, "skipped_links": skipped})
    except BaseException:
        output.close()
        raise

    def chunks():
        try:
            while data := output.read(CHUNK):
                yield data
        finally:
            output.close()

    return StreamingResponse(chunks(), media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(root_name + ".zip", safe=""),
                 "Content-Length": str(size), "X-Skipped-Links": str(skipped),
                 "X-Content-Type-Options": "nosniff"}, background=BackgroundTask(output.close))


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)
    destination: str = Field(default="", max_length=4096)
    mode: str = Field(default="0644", pattern=r"^[0-7]{3,4}$")


@router.post("/{kind}/{identity}/{operation}")
def mutate(kind: Kind, identity: int, operation: Literal["mkdir", "rename", "chmod", "delete"],
           body: Operation, p: Principal = Depends(require("sftp.write")),
           db: Session = Depends(get_db)):
    row = owned(db, kind, identity, p)
    path = path_value(body.path)
    with connection(row) as client:
        if operation == "mkdir":
            client.mkdir(path)
        elif operation == "rename":
            destination = path_value(body.destination)
            if existing(client, destination):
                raise HTTPException(409, "Destination already exists; rename never overwrites files")
            client.rename(path, destination)
        elif operation == "chmod":
            client.chmod(path, int(body.mode, 8))
        else:
            if path.rstrip("/") in ("", ".", ".."):
                raise HTTPException(422, "Select a file or empty directory; root cannot be removed")
            entry = client.lstat(path)
            if stat.S_ISDIR(entry.st_mode):
                if next(client.listdir_iter(path, read_aheads=1), None) is not None:
                    raise HTTPException(409, "Directory is not empty; remove its contents first")
                client.rmdir(path)  # Non-empty directories fail; never recurse.
            else:
                client.remove(path)
    write_audit(db, p, "sftp." + operation, row.host,
                details=body.model_dump(exclude_defaults=True))
    return {"ok": True}
