"""Single startup path for the worker: pairing code, TLS material, then uvicorn.

Interactive use:  python -m app.launcher   (run-worker.ps1 does this)
Unattended use:   unattended-worker.py calls serve() with a protected state directory.
"""

from __future__ import annotations

import getpass
import os
import secrets
import socket
import sys
from pathlib import Path

WORKER_DIRECTORY = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIRECTORY = WORKER_DIRECTORY / "worker-state"
# No 0/O or 1/I/L: the code is read from one screen and typed on another.
_PAIRING_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_RULE = "=" * 64


def new_pairing_code(length: int = 12) -> str:
    return "".join(secrets.choice(_PAIRING_ALPHABET) for _ in range(length))


def _run_as() -> str:
    domain = os.environ.get("USERDOMAIN", "")
    try:
        user = getpass.getuser()
    except (OSError, KeyError):
        user = os.environ.get("USERNAME", "unknown")
    return f"{domain}\\{user}" if domain else user


def _write_text_atomically(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _banner(settings, material, pairing_code: str | None) -> str:
    from . import __version__

    scheme = "https" if material else "http"
    host = settings.listen_host
    if host in ("0.0.0.0", "::", ""):
        host = socket.getfqdn()
    lines = [
        "",
        _RULE,
        f" RSAT Full Windows Worker {__version__}",
        _RULE,
        f" Worker URL:      {scheme}://{host}:{settings.listen_port}",
    ]
    if pairing_code:
        minutes = settings.pairing_ttl_seconds // 60
        lines.append(f" Pairing code:    {pairing_code}")
        lines.append(f"                  single use, expires after {minutes} minutes")
    if material:
        origin = "self-signed, created by this worker" if material.self_signed else "configured"
        lines.append(f" TLS SHA-256:     {material.fingerprint}")
        lines.append(
            f"                  {origin}; valid until {material.not_after:%Y-%m-%d}."
            " Compare it in Settings when pairing."
        )
        if material.created:
            lines.append("                  NEW certificate: an earlier pairing must be repeated.")
    else:
        lines += [
            " TLS:             DISABLED (ALLOW_INSECURE_HTTP=true)",
            " WARNING: the worker credential, new passwords and directory data cross",
            " WARNING: the network unencrypted. Use only on an isolated lab segment.",
        ]
    lines += [f" Run-as identity: {_run_as()}", _RULE, ""]
    return "\n".join(lines)


def serve(
    *,
    pairing_code: str,
    pairing_code_file: str = "",
    state_directory: Path | None = None,
    show_pairing_code: bool = True,
) -> None:
    """Start the worker. Imports are deferred so the caller can chdir to .env first."""
    from . import tls
    from .config import settings

    if not settings.token_initialized:
        raise SystemExit(
            "The worker channel credential is not initialized. Run run-worker.ps1 once first."
        )
    tls_directory = (Path(state_directory) if state_directory else DEFAULT_STATE_DIRECTORY) / "tls"
    try:
        material = tls.resolve(settings, tls_directory)
    except tls.TlsConfigurationError as exc:
        raise SystemExit(f"TLS configuration error: {exc}") from exc
    tls.activate(material)
    settings.pairing_code = pairing_code
    settings.pairing_code_file = pairing_code_file

    print(_banner(settings, material, pairing_code if show_pairing_code else None), flush=True)
    if not material:
        print("WARNING: serving plain HTTP because ALLOW_INSECURE_HTTP=true.", file=sys.stderr)
    if state_directory and material:
        # The fingerprint is public; the unattended operator reads it beside the code.
        _write_text_atomically(Path(state_directory) / "tls-fingerprint.txt", material.fingerprint)

    import uvicorn

    from .main import app

    options = {"host": settings.listen_host, "port": settings.listen_port}
    if material:
        options["ssl_certfile"] = str(material.cert_file)
        options["ssl_keyfile"] = str(material.key_file)
    uvicorn.run(app, **options)


def main() -> None:
    os.chdir(WORKER_DIRECTORY)  # The deployment .env lives beside the package.
    from .config import settings

    serve(pairing_code=settings.pairing_code.strip() or new_pairing_code())


if __name__ == "__main__":
    main()
