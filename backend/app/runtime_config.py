from dataclasses import dataclass
from .config import settings
from .db import SessionLocal, SystemSetting

@dataclass
class RuntimeConfig:
    demo_mode: bool
    worker_url: str
    worker_token: str

def get_runtime_config() -> RuntimeConfig:
    with SessionLocal() as db:
        rows = {x.key: x.value for x in db.query(SystemSetting).all()}
    return RuntimeConfig(
        demo_mode=(rows.get("demo_mode", str(settings.demo_mode)).lower() == "true"),
        worker_url=rows.get("worker_url", settings.worker_url).rstrip("/"),
        worker_token=rows.get("worker_token", settings.worker_token),
    )
