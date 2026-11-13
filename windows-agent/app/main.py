import hmac
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import __version__, tls
from .common import IDENTITY_SCRIPT
from .config import settings
from .routers import ad, admin, domain, gpo, network
from .runner import run_ps

MODULE_PROBE = r"""$m=@('ActiveDirectory','DnsServer','DhcpServer','GroupPolicy')
$r=@{}
foreach($x in $m){$r[$x]=[bool](Get-Module -ListAvailable $x)}
$r | ConvertTo-Json -Compress
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The launcher prepares TLS. Starting the API some other way must not
    # quietly expose the worker credential and new passwords over plain HTTP.
    if tls.active() is None and not settings.allow_insecure_http:
        raise RuntimeError(
            "Start the worker with run-worker.ps1 (python -m app.launcher) so it serves HTTPS. "
            "Plain HTTP requires ALLOW_INSECURE_HTTP=true."
        )
    yield


app = FastAPI(title="RSAT Windows Worker", version=__version__, lifespan=lifespan)

_pairing_started = time.monotonic()
_pairing_used = False
_pairing_attempts = 0
_pairing_lock = threading.Lock()
_modules_lock = threading.Lock()
_modules_cache: tuple[float, dict] | None = None


class PairRequest(BaseModel):
    code: str = Field(min_length=4, max_length=128)


def _same_secret(supplied: str, expected: str) -> bool:
    """Constant-time comparison that also accepts non-ASCII input without raising."""
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


@app.middleware("http")
async def token_gate(request: Request, call_next):
    if request.url.path in {"/health", "/pair"}:
        return await call_next(request)
    supplied = request.headers.get("authorization", "")
    if not settings.token_initialized or not _same_secret(
        supplied, f"Bearer {settings.agent_token}"
    ):
        return JSONResponse(status_code=401, content={"detail": "Invalid worker credential"})
    return await call_next(request)


@app.post("/pair")
def pair(body: PairRequest):
    global _pairing_used, _pairing_attempts
    with _pairing_lock:
        if _pairing_used:
            raise HTTPException(
                status_code=409,
                detail="Pairing code already used. Restart the worker to generate a new code.",
            )
        if time.monotonic() - _pairing_started > settings.pairing_ttl_seconds:
            raise HTTPException(
                status_code=410,
                detail="Pairing code expired. Restart the worker to generate a new code.",
            )
        if _pairing_attempts >= 10:
            raise HTTPException(
                status_code=429, detail="Too many pairing attempts. Restart the worker."
            )
        _pairing_attempts += 1
        expected = settings.pairing_code.strip()
        if not expected or not _same_secret(body.code.strip(), expected):
            raise HTTPException(status_code=401, detail="Invalid pairing code")
        if not settings.token_initialized:
            raise HTTPException(status_code=503, detail="Worker secret is not initialized")
        identity = run_ps(IDENTITY_SCRIPT)
        _pairing_used = True
    if settings.pairing_code_file:
        try:
            Path(settings.pairing_code_file).unlink(missing_ok=True)
        except OSError:
            pass  # The already-consumed code cannot be used again.
    material = tls.active()
    return {
        "ok": True,
        "worker_token": settings.agent_token,
        "identity": identity,
        "pairing_ttl_seconds": settings.pairing_ttl_seconds,
        "version": __version__,
        "tls": material is not None,
        "tls_fingerprint_sha256": material.fingerprint if material else "",
    }


app.include_router(domain.router)
app.include_router(ad.router)
app.include_router(network.router)
app.include_router(gpo.router)
app.include_router(admin.router)


def _available_modules() -> dict:
    """RSAT module availability, probed at most once per cache interval.

    /health needs no credential, so it must not start a PowerShell process on
    every anonymous request.
    """
    global _modules_cache
    with _modules_lock:
        now = time.monotonic()
        if _modules_cache and now < _modules_cache[0]:
            return _modules_cache[1]
        modules = run_ps(MODULE_PROBE)
        _modules_cache = (now + settings.health_cache_seconds, modules)
        return modules


@app.get("/health")
def health():
    material = tls.active()
    return {
        "status": "ok",
        "service": "windows-worker",
        "version": __version__,
        "modules": _available_modules(),
        "pairing_available": bool(settings.pairing_code) and not _pairing_used,
        "tls": material is not None,
        "tls_fingerprint_sha256": material.fingerprint if material else "",
    }
