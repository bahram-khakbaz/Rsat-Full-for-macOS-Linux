"""Transport security for the optional Windows worker.

The worker credential, new account passwords and password resets travel over
this channel, so it must be HTTPS. A worker normally presents a self-signed
certificate; its SHA-256 fingerprint is compared by the operator at pairing and
the certificate is then pinned. A certificate issued by a CA the backend
already trusts is accepted without pinning.
"""

import re
import socket
import ssl
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from fastapi import HTTPException

from .config import settings

INSECURE_MESSAGE = (
    "The worker URL must use https://. Plain HTTP exposes the worker credential and "
    "account passwords on the network; set ALLOW_INSECURE_WORKER=true only on an "
    "isolated, trusted segment."
)


def normalize_url(value: str) -> str:
    """Validate a worker base URL and return it without a trailing slash."""
    url = value.strip().rstrip("/")
    parts = urlsplit(url)
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.path
        or parts.query
        or parts.fragment
    ):
        raise HTTPException(422, "Enter the worker URL as https://host:port without a path")
    try:
        parts.port  # noqa: B018 - accessing the property validates the port
    except ValueError as exc:
        raise HTTPException(422, "The worker URL has an invalid port") from exc
    return url


def normalize_fingerprint(value: str) -> str:
    digest = re.sub(r"[\s:]", "", value).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise HTTPException(422, "Enter the SHA-256 certificate fingerprint shown by the worker")
    return digest


def format_fingerprint(digest: str) -> str:
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


def certificate_summary(pem: str) -> dict:
    cert = x509.load_pem_x509_certificate(pem.encode("ascii"))
    return {
        "fingerprint": format_fingerprint(cert.fingerprint(hashes.SHA256()).hex()),
        "subject": cert.subject.rfc4514_string(),
        "valid_from": cert.not_valid_before_utc.isoformat(),
        "valid_until": cert.not_valid_after_utc.isoformat(),
    }


def inspect(url: str) -> dict:
    """Fetch the certificate a worker presents. No credential is sent."""
    parts = urlsplit(normalize_url(url))
    if parts.scheme != "https":
        raise HTTPException(409, INSECURE_MESSAGE)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((parts.hostname, parts.port or 443), timeout=6) as sock:
            with context.wrap_socket(sock, server_hostname=parts.hostname) as tls:
                der = tls.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as exc:
        raise HTTPException(
            502, "Cannot read the worker certificate. Check the URL, port and that TLS is enabled."
        ) from exc
    pem = ssl.DER_cert_to_PEM_cert(der)
    return {"pem": pem, **certificate_summary(pem)}


def pinned_context(pem: str) -> ssl.SSLContext:
    """Trust exactly the pinned worker certificate (or a chain issued by it)."""
    context = ssl.create_default_context(cadata=pem)
    # The pin identifies the worker; a self-signed certificate often has no
    # name matching the address the operator entered.
    context.check_hostname = False
    return context


def verify_option(url: str, pem: str) -> ssl.SSLContext | bool:
    """Return the httpx ``verify`` value for a worker URL, or refuse plain HTTP."""
    scheme = urlsplit(url).scheme
    if scheme == "https":
        return pinned_context(pem) if pem else True
    if scheme == "http" and settings.allow_insecure_worker:
        return True
    raise HTTPException(409, INSECURE_MESSAGE)


def mode(url: str, pem: str) -> str:
    if not url:
        return "none"
    if urlsplit(url).scheme != "https":
        return "insecure"
    return "pinned" if pem else "ca"
