import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import settings
from .db import SessionLocal, SshLinuxServer, SshSwitch, SystemSetting, init_db
from .routers import (
    ad,
    audit,
    auth,
    domain,
    gpo,
    ipam,
    linux_servers,
    network,
    network_settings,
    operators,
    sftp,
    ssh,
)
from .routers import settings as settings_router
from .secret_store import needs_rotation, rotate_secret

log = logging.getLogger(__name__)
ENCRYPTED_SETTINGS = ("worker_token", "native_password")


def check_configuration() -> None:
    """Refuse to serve a production deployment protected by placeholder secrets."""
    for warning in settings.weak_settings():
        log.warning("Configuration: %s", warning)
    problems = settings.placeholder_secrets()
    if not problems:
        return
    message = "Insecure configuration: set " + "; ".join(problems)
    if settings.is_production:
        raise RuntimeError(message)
    log.warning("%s. This is only acceptable for local development.", message)


def rotate_stored_credentials() -> int:
    """Re-encrypt stored credentials that are not under the primary key."""
    changed = 0
    with SessionLocal() as db:
        for row in db.query(SystemSetting).filter(SystemSetting.key.in_(ENCRYPTED_SETTINGS)):
            if needs_rotation(row.value):
                row.value = rotate_secret(row.value)
                changed += 1
        for model in (SshSwitch, SshLinuxServer):
            for row in db.query(model):
                if needs_rotation(row.password):
                    row.password = rotate_secret(row.password)
                    changed += 1
        if changed:
            db.commit()
    return changed


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_configuration()
    init_db()
    try:
        rotated = rotate_stored_credentials()
        if rotated:
            log.info("Re-encrypted %d stored credential(s) with the primary key", rotated)
    except Exception:  # Never block start-up: values stay readable with the old key.
        log.exception("Stored credentials could not be re-encrypted")
    yield


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Validation errors may contain the supplied password in `input` or `ctx`.
    # Return only field names and validation messages, never rejected values.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {
                    "loc": list(error.get("loc", [])),
                    "type": error.get("type", "validation_error"),
                    "msg": error.get("msg", "Invalid value"),
                }
                for error in exc.errors()
            ]
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
for module in (
    ssh,
    linux_servers,
    ipam,
    sftp,
    network_settings,
    auth,
    operators,
    domain,
    ad,
    network,
    gpo,
    audit,
    settings_router,
):
    app.include_router(module.router)


@app.get("/api/health")
def health():
    from .runtime_config import get_runtime_config

    runtime = get_runtime_config()
    return {
        "status": "ok",
        "service": "backend",
        "demo_mode": runtime.demo_mode,
        "version": __version__,
        "connection_mode": runtime.connection_mode,
    }
