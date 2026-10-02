from dataclasses import dataclass
from .config import settings
from .db import SessionLocal, SystemSetting
from .secret_store import decrypt_secret

@dataclass
class RuntimeConfig:
    demo_mode: bool
    worker_url: str
    worker_token: str

def get_runtime_config() -> RuntimeConfig:
    with SessionLocal() as db:
        rows = {x.key: x.value for x in db.query(SystemSetting).all()}
    token_value = rows.get("worker_token")
    token = decrypt_secret(token_value) if token_value is not None else settings.worker_token
    return RuntimeConfig(
        demo_mode=(rows.get("demo_mode", str(settings.demo_mode)).lower() == "true"),
        worker_url=rows.get("worker_url", settings.worker_url).rstrip("/"),
        worker_token=token,
    )
