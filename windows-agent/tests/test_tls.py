"""Listener certificate lifecycle and the fingerprint format the control plane pins."""

import hashlib
import os
import re
import socket
import ssl
import threading
from types import SimpleNamespace

import pytest

from app import tls

FINGERPRINT = re.compile(r"[0-9a-f]{2}(:[0-9a-f]{2}){31}")


def settings(**changes):
    values = {
        "allow_insecure_http": False,
        "tls_cert_file": "",
        "tls_key_file": "",
        "tls_state_dir": "",
        "tls_san": "",
        "listen_host": "0.0.0.0",
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_self_signed_certificate_is_created_once_and_reused(tmp_path):
    directory = tmp_path / "tls"
    first = tls.resolve(settings(tls_san="rsat-worker.example.com,192.0.2.10"), directory)
    assert first.created and first.self_signed
    assert FINGERPRINT.fullmatch(first.fingerprint)
    pem = first.cert_file.read_text()
    der = ssl.PEM_cert_to_DER_cert(pem)
    digest = hashlib.sha256(der).hexdigest()
    assert first.fingerprint.replace(":", "") == digest

    second = tls.resolve(settings(), directory)
    assert not second.created and second.fingerprint == first.fingerprint
    if os.name != "nt":
        assert first.key_file.stat().st_mode & 0o077 == 0
        assert directory.stat().st_mode & 0o077 == 0
    assert sorted(path.name for path in directory.iterdir()) == sorted(
        [tls.KEY_NAME, tls.CERT_NAME]
    )


def test_generated_certificate_is_a_usable_pinnable_server_certificate(tmp_path):
    from cryptography import x509

    material = tls.resolve(settings(tls_san="rsat-worker.example.com,192.0.2.10"), tmp_path)
    certificate = x509.load_pem_x509_certificate(material.cert_file.read_bytes())
    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "rsat-worker.example.com" in names.get_values_for_type(x509.DNSName)
    assert "localhost" in names.get_values_for_type(x509.DNSName)
    assert "192.0.2.10" in [str(ip) for ip in names.get_values_for_type(x509.IPAddress)]
    assert not certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca

    # The server side loads the pair; a client that trusts exactly this
    # certificate (what the control plane stores at pairing) accepts it.
    ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(material.cert_file, material.key_file)
    client = ssl.create_default_context(cadata=material.cert_file.read_text())
    assert client.verify_mode == ssl.CERT_REQUIRED


def _messages(error):
    nested = [text for inner in getattr(error, "exceptions", ()) for text in _messages(inner)]
    return [str(error), *nested]


def _serve_once(listener, context):
    try:
        connection, _ = listener.accept()
        with context.wrap_socket(connection, server_side=True) as channel:
            channel.sendall(b"ok")
    except OSError:
        pass  # The refusing client below ends the handshake.


def test_only_the_pinned_certificate_completes_a_real_handshake(tmp_path):
    material = tls.resolve(settings(), tmp_path / "worker")
    other = tls.resolve(settings(), tmp_path / "other")
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(material.cert_file, material.key_file)

    def connect(trusted_pem):
        with socket.create_server(("127.0.0.1", 0)) as listener:
            thread = threading.Thread(target=_serve_once, args=(listener, server), daemon=True)
            thread.start()
            client = ssl.create_default_context(cadata=trusted_pem)
            try:
                with socket.create_connection(listener.getsockname(), timeout=10) as raw:
                    with client.wrap_socket(raw, server_hostname="localhost") as channel:
                        peer = channel.getpeercert(binary_form=True)
                        return channel.recv(2), tls.format_fingerprint(peer)
            finally:
                thread.join(10)

    assert connect(material.cert_file.read_text()) == (b"ok", material.fingerprint)
    with pytest.raises(ssl.SSLError):
        connect(other.cert_file.read_text())


def test_expiring_or_damaged_material_is_replaced(tmp_path, monkeypatch):
    first = tls.resolve(settings(), tmp_path)
    monkeypatch.setattr(tls, "RENEW_BEFORE_DAYS", tls.VALIDITY_DAYS + 1)
    renewed = tls.resolve(settings(), tmp_path)
    assert renewed.created and renewed.fingerprint != first.fingerprint
    monkeypatch.undo()
    (tmp_path / tls.KEY_NAME).write_text("not a key")
    repaired = tls.resolve(settings(), tmp_path)
    assert repaired.created and repaired.fingerprint != renewed.fingerprint


def test_configured_certificate_is_used_as_is(tmp_path):
    generated = tls.resolve(settings(), tmp_path / "generated")
    configured = tls.resolve(
        settings(
            tls_cert_file=str(generated.cert_file),
            tls_key_file=str(generated.key_file),
        ),
        tmp_path / "unused",
    )
    assert not configured.self_signed and not configured.created
    assert configured.fingerprint == generated.fingerprint
    assert not (tmp_path / "unused").exists()


def test_incomplete_or_mismatched_configuration_is_an_error(tmp_path):
    first = tls.resolve(settings(), tmp_path / "one")
    second = tls.resolve(settings(), tmp_path / "two")
    for changes in (
        {"tls_cert_file": str(first.cert_file)},
        {"tls_key_file": str(first.key_file)},
        {"tls_cert_file": str(first.cert_file), "tls_key_file": str(second.key_file)},
        {"tls_cert_file": str(tmp_path / "missing.pem"), "tls_key_file": str(first.key_file)},
    ):
        with pytest.raises(tls.TlsConfigurationError):
            tls.resolve(settings(**changes), tmp_path / "unused")


def test_plain_http_only_when_explicitly_allowed(tmp_path):
    assert tls.resolve(settings(allow_insecure_http=True), tmp_path / "tls") is None
    assert not (tmp_path / "tls").exists()


def test_startup_guard_refuses_plain_http_without_opt_in(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main as worker

    monkeypatch.setattr(worker.settings, "allow_insecure_http", False)
    tls.activate(None)
    with pytest.raises(Exception) as error:  # noqa: B017 - may arrive inside an exception group
        with TestClient(worker.app):
            pass
    assert any("HTTPS" in message for message in _messages(error.value))
    monkeypatch.setattr(worker.settings, "allow_insecure_http", True)
    with TestClient(worker.app):
        pass
