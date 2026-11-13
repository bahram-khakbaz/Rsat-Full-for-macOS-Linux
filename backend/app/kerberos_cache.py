"""Private short-lived Kerberos credentials for direct service operations.

A ticket is obtained with ``kinit`` into a private temporary directory and
reused for a few minutes, so a burst of DNS/DHCP calls does not authenticate
against the KDC once per request. Tickets never leave the backend process
environment and are removed when they expire or the saved account changes.
"""

import hashlib
import os
import re
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import HTTPException

TICKET_LIFETIME = "5m"
# Reuse well inside the ticket lifetime so an operation never starts with a
# ticket that is about to expire.
REUSE_SECONDS = 180

_lock = threading.Lock()
_failures: set[str] = set()
_tickets: dict[str, "_Ticket"] = {}


@dataclass
class _Ticket:
    directory: tempfile.TemporaryDirectory
    env: dict[str, str]
    expires: float


def _discard(key: str) -> None:
    ticket = _tickets.pop(key, None)
    if ticket is not None:
        ticket.directory.cleanup()


def reset_failures() -> None:
    """Forget rejected credentials and cached tickets (the saved account changed)."""
    with _lock:
        _failures.clear()
        for key in list(_tickets):
            _discard(key)


def _acquire(domain: str, username: str, kdc: str, password: str, key: str) -> _Ticket:
    directory = tempfile.TemporaryDirectory(prefix="rsat-service-")
    try:
        path = directory.name + "/krb5.conf"
        with open(path, "w") as handle:
            handle.write(
                "[libdefaults]\n"
                f" default_realm = {domain}\n"
                " dns_lookup_kdc = false\n"
                " dns_lookup_realm = false\n"
                " rdns = false\n"
                " udp_preference_limit = 1\n"
                "[realms]\n"
                f" {domain} = {{\n"
                f"  kdc = {kdc}\n"
                " }\n"
            )
        env = os.environ.copy()
        env.update(KRB5_CONFIG=path, KRB5CCNAME="FILE:" + directory.name + "/ticket")
        try:
            result = subprocess.run(
                ["kinit", "-l", TICKET_LIFETIME, username + "@" + domain],
                input=password + "\n",
                text=True,
                capture_output=True,
                env=env,
                timeout=12,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(504, "Kerberos KDC timed out. Check VPN and port 88.") from exc
        if result.returncode:
            error = result.stderr.lower()
            if "preauthentication failed" in error or "password incorrect" in error:
                _failures.add(key)
            raise HTTPException(
                502,
                "Kerberos login failed. Check saved domain account, time and VPN. "
                "No NTLM fallback was attempted.",
            )
    except BaseException:
        directory.cleanup()
        raise
    return _Ticket(directory, env, time.monotonic() + REUSE_SECONDS)


@contextmanager
def credential_cache(cfg):
    """Yield a process environment whose KRB5CCNAME holds a valid ticket."""
    domain = cfg.get("domain", "").upper()
    username = cfg.get("username", "").split("@")[0].split("\\")[-1]
    kdc = cfg.get("preferred_dc") or next(iter(cfg.get("hosts", [])), "")
    password = cfg.get("password", "")
    if not domain or not username or not password:
        raise HTTPException(409, "Save your domain account in Settings first.")
    if not re.fullmatch(r"[A-Z0-9.-]+", domain) or not re.fullmatch(r"[a-zA-Z0-9.-]+", kdc):
        raise HTTPException(422, "Invalid domain or KDC hostname")
    key = hashlib.sha256(f"{username}@{domain}\0{kdc}\0{password}".encode()).hexdigest()
    with _lock:
        if key in _failures:
            raise HTTPException(
                422,
                "AD rejected these credentials. Update the saved domain password before retrying.",
            )
        ticket = _tickets.get(key)
        if ticket is None or ticket.expires <= time.monotonic():
            _discard(key)
            # One account is active at a time; drop tickets of previous settings.
            for stale in list(_tickets):
                _discard(stale)
            ticket = _acquire(domain, username, kdc, password, key)
            _tickets[key] = ticket
        try:
            yield dict(ticket.env)
        except BaseException:
            # The ticket may be the cause (revoked, clock skew); start fresh next time.
            _discard(key)
            raise
