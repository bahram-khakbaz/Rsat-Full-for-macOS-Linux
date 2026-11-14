"""TLS material for the worker listener.

The worker serves HTTPS with either an operator-supplied certificate or a
self-signed certificate it creates once and reuses. The control plane pins that
certificate during pairing, after the operator compares its SHA-256 fingerprint.
"""

from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import os
import socket
import ssl
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

CERT_NAME = "worker-cert.pem"
KEY_NAME = "worker-key.pem"
VALIDITY_DAYS = 1095
RENEW_BEFORE_DAYS = 30


class TlsConfigurationError(RuntimeError):
    """The configured or stored TLS material cannot be used."""


@dataclass(frozen=True)
class TlsMaterial:
    cert_file: Path
    key_file: Path
    fingerprint: str
    not_after: datetime
    self_signed: bool
    created: bool = False


# Set by the launcher; read by /health and the startup guard.
_active: TlsMaterial | None = None


def activate(material: TlsMaterial | None) -> None:
    global _active
    _active = material


def active() -> TlsMaterial | None:
    return _active


def format_fingerprint(der: bytes) -> str:
    """SHA-256 of the DER certificate as lowercase, colon-separated hex."""
    digest = hashlib.sha256(der).hexdigest()
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


def inspect(cert_file: Path) -> tuple[str, datetime]:
    """Fingerprint and expiry of the leaf (first) certificate in a PEM file."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    try:
        certificate = x509.load_pem_x509_certificate(Path(cert_file).read_bytes())
    except (OSError, ValueError) as exc:
        raise TlsConfigurationError(f"Cannot read TLS certificate {cert_file}") from exc
    der = certificate.public_bytes(serialization.Encoding.DER)
    return format_fingerprint(der), certificate.not_valid_after_utc


def _pair_is_usable(cert_file: Path, key_file: Path) -> bool:
    try:
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(str(cert_file), str(key_file))
    except (OSError, ssl.SSLError, ValueError):
        return False
    return True


def _current_sid() -> str:
    try:
        result = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    row = next(csv.reader(io.StringIO(result.stdout.strip())), [])
    sid = row[1].strip() if len(row) > 1 else ""
    return sid if sid.startswith("S-1-") else ""


def restrict_directory(directory: Path) -> bool:
    """Limit a directory to the worker account, SYSTEM and Administrators.

    Returns False when the access control list could not be applied; the caller
    warns the operator instead of failing, because Python can only do this on a
    best-effort basis on Windows.
    """
    if os.name != "nt":
        os.chmod(directory, 0o700)
        return True
    sid = _current_sid()
    if not sid:
        return False
    inherit = "(OI)(CI)F"
    grants = [f"*{sid}:{inherit}", f"*S-1-5-18:{inherit}", f"*S-1-5-32-544:{inherit}"]
    try:
        result = subprocess.run(
            ["icacls", str(directory), "/inheritance:r", "/grant:r", *grants],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _write_private(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".new")
    temporary.unlink(missing_ok=True)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    os.replace(temporary, path)


def _subject_names(listen_host: str, extra: str) -> tuple[str, list[str], list]:
    """Common name, DNS names and IP addresses for the certificate."""
    hostname = socket.gethostname()
    fqdn = socket.getfqdn()
    candidates = [fqdn, hostname, os.environ.get("COMPUTERNAME", ""), "localhost"]
    addresses = ["127.0.0.1", "::1", listen_host]
    try:
        addresses.extend(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass
    for item in extra.replace(";", ",").split(","):
        (addresses if _is_ip(item.strip()) else candidates).append(item.strip())

    names: list[str] = []
    for candidate in candidates:
        try:
            name = candidate.strip().rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError:
            continue
        if name and not _is_ip(name) and name not in names:
            names.append(name)
    ips = []
    for address in addresses:
        if _is_ip(address):
            parsed = ipaddress.ip_address(address.strip())
            if not parsed.is_unspecified and parsed not in ips:
                ips.append(parsed)
    return (names[0] if names else "rsat-worker")[:64], names, ips


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return True


def generate_self_signed(directory: Path, listen_host: str = "", extra_names: str = ""):
    """Create a P-256 key and a self-signed server certificate in `directory`."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    common_name, dns_names, ips = _subject_names(listen_host, extra_names)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "RSAT Full Windows Worker"),
        ]
    )
    alternative = [x509.DNSName(name) for name in dns_names]
    alternative += [x509.IPAddress(address) for address in ips]
    now = datetime.now(timezone.utc)
    public_key = key.public_key()
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        # No keyUsage extension: a pinned self-signed leaf must stay acceptable as
        # its own trust anchor to TLS stacks that insist on keyCertSign otherwise.
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName(alternative), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(public_key), critical=False
        )
        .sign(key, hashes.SHA256())
    )
    directory.mkdir(parents=True, exist_ok=True)
    restricted = restrict_directory(directory)
    _write_private(
        directory / KEY_NAME,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    _write_private(directory / CERT_NAME, certificate.public_bytes(serialization.Encoding.PEM))
    return restricted


def ensure_self_signed(directory: Path, listen_host: str = "", extra_names: str = ""):
    """Reuse the stored certificate, or create one when missing, broken or expiring."""
    cert_file, key_file = directory / CERT_NAME, directory / KEY_NAME
    if cert_file.is_file() and key_file.is_file() and _pair_is_usable(cert_file, key_file):
        fingerprint, not_after = inspect(cert_file)
        if not_after - datetime.now(timezone.utc) > timedelta(days=RENEW_BEFORE_DAYS):
            return TlsMaterial(cert_file, key_file, fingerprint, not_after, self_signed=True)
    restricted = generate_self_signed(directory, listen_host, extra_names)
    if not restricted:
        print(
            f"WARNING: could not restrict access to {directory}. Limit that directory to the "
            "worker account and administrators; it holds the worker's TLS private key.",
            file=sys.stderr,
        )
    fingerprint, not_after = inspect(cert_file)
    return TlsMaterial(cert_file, key_file, fingerprint, not_after, self_signed=True, created=True)


def resolve(settings, default_directory: Path) -> TlsMaterial | None:
    """TLS material for this start, or None only when plain HTTP was requested."""
    if settings.allow_insecure_http:
        return None
    cert, key = settings.tls_cert_file.strip(), settings.tls_key_file.strip()
    if bool(cert) != bool(key):
        raise TlsConfigurationError("Set both TLS_CERT_FILE and TLS_KEY_FILE, or neither")
    if cert:
        cert_file, key_file = Path(cert), Path(key)
        if not _pair_is_usable(cert_file, key_file):
            raise TlsConfigurationError(
                "TLS_CERT_FILE and TLS_KEY_FILE are missing, unreadable or do not match"
            )
        fingerprint, not_after = inspect(cert_file)
        return TlsMaterial(cert_file, key_file, fingerprint, not_after, self_signed=False)
    directory = Path(settings.tls_state_dir.strip() or default_directory)
    return ensure_self_signed(directory, settings.listen_host, settings.tls_san)
