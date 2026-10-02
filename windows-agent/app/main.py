import secrets
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .config import settings
from .runner import run_ps
from .routers import ad, domain, gpo, network

app = FastAPI(title="RSAT Windows Worker", version="0.3.0")

@app.middleware("http")
async def token_gate(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    supplied = request.headers.get("authorization", "")
    if not secrets.compare_digest(supplied, f"Bearer {settings.agent_token}"):
        return JSONResponse(status_code=401, content={"detail":"Invalid worker token"})
    return await call_next(request)

app.include_router(domain.router)
app.include_router(ad.router)
app.include_router(network.router)
app.include_router(gpo.router)

@app.get("/health")
def health():
    modules = run_ps(r"""$m=@('ActiveDirectory','DnsServer','DhcpServer','GroupPolicy')
$r=@{}
foreach($x in $m){$r[$x]=[bool](Get-Module -ListAvailable $x)}
$r | ConvertTo-Json -Compress
""")
    return {"status":"ok","service":"windows-worker","version":"0.3.0","modules":modules}
