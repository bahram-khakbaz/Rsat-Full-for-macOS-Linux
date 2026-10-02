import secrets
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .config import settings
from .runner import run_ps
from .routers import ad, domain, gpo, network, admin

app = FastAPI(title="RSAT Windows Worker", version="0.4.0")

_pairing_started = time.monotonic()
_pairing_used = False
_pairing_attempts = 0

class PairRequest(BaseModel):
    code: str = Field(min_length=4, max_length=128)

@app.middleware("http")
async def token_gate(request: Request, call_next):
    if request.url.path in {"/health", "/pair"}:
        return await call_next(request)
    supplied = request.headers.get("authorization", "")
    if not secrets.compare_digest(supplied, f"Bearer {settings.agent_token}"):
        return JSONResponse(status_code=401, content={"detail":"Invalid worker credential"})
    return await call_next(request)

@app.post("/pair")
def pair(body: PairRequest):
    global _pairing_used, _pairing_attempts
    if _pairing_used:
        raise HTTPException(status_code=409, detail="Pairing code already used. Restart the worker to generate a new code.")
    if time.monotonic() - _pairing_started > settings.pairing_ttl_seconds:
        raise HTTPException(status_code=410, detail="Pairing code expired. Restart the worker to generate a new code.")
    if _pairing_attempts >= 10:
        raise HTTPException(status_code=429, detail="Too many pairing attempts. Restart the worker.")
    _pairing_attempts += 1
    if not settings.pairing_code or not secrets.compare_digest(body.code.strip(), settings.pairing_code.strip()):
        raise HTTPException(status_code=401, detail="Invalid pairing code")
    if not settings.agent_token or settings.agent_token == "change-me":
        raise HTTPException(status_code=503, detail="Worker secret is not initialized")
    identity = run_ps(r"""$who=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$domain=''
try { Import-Module ActiveDirectory; $domain=(Get-ADDomain).DNSRoot } catch {}
[pscustomobject]@{runAs=$who;computer=$env:COMPUTERNAME;domain=$domain} | ConvertTo-Json -Compress
""")
    _pairing_used = True
    return {
        "ok": True,
        "worker_token": settings.agent_token,
        "identity": identity,
        "pairing_ttl_seconds": settings.pairing_ttl_seconds,
    }

app.include_router(domain.router)
app.include_router(ad.router)
app.include_router(network.router)
app.include_router(gpo.router)
app.include_router(admin.router)

@app.get("/health")
def health():
    modules = run_ps(r"""$m=@('ActiveDirectory','DnsServer','DhcpServer','GroupPolicy')
$r=@{}
foreach($x in $m){$r[$x]=[bool](Get-Module -ListAvailable $x)}
$r | ConvertTo-Json -Compress
""")
    return {
        "status":"ok",
        "service":"windows-worker",
        "version":"0.4.0",
        "modules":modules,
        "pairing_available": bool(settings.pairing_code) and not _pairing_used,
    }
