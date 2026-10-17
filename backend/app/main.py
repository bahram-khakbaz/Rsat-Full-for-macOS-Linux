from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .config import settings
from .db import init_db
from .routers import ipam, sftp, linux_servers, ssh, network_settings, auth, ad, network, gpo, audit, domain, settings as settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Validation errors may contain the supplied password in `input` or `ctx`.
    # Return only field names and validation messages, never rejected values.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(error.get("loc", [])), "type": error.get("type", "validation_error"),
         "msg": error.get("msg", "Invalid value")}
        for error in exc.errors()
    ]})
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ssh.router)
app.include_router(linux_servers.router)
app.include_router(ipam.router)
app.include_router(sftp.router)
app.include_router(network_settings.router)
app.include_router(auth.router)
app.include_router(domain.router)
app.include_router(ad.router)
app.include_router(network.router)
app.include_router(gpo.router)
app.include_router(audit.router)
app.include_router(settings_router.router)

@app.get("/api/health")
def health():
    from .runtime_config import get_runtime_config
    runtime = get_runtime_config()
    return {"status":"ok","service":"backend","demo_mode":runtime.demo_mode,"version":"0.4.0","connection_mode":runtime.connection_mode}
