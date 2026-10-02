from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .db import init_db
from .routers import auth, ad, network, gpo, audit, domain, settings as settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
    return {"status":"ok","service":"backend","demo_mode":runtime.demo_mode,"version":"0.3.0"}
