import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

UNINITIALIZED_TOKENS = frozenset(
    {"", "change-me", "replace-with-a-long-random-token", "__AUTO_GENERATED__"}
)


class Settings(BaseSettings):
    agent_token: str = "change-me"
    pairing_code: str = ""
    pairing_code_file: str = ""
    pairing_ttl_seconds: int = 900
    listen_host: str = "0.0.0.0"
    listen_port: int = 8765
    powershell_exe: str = "powershell.exe"
    max_output_bytes: int = 4_000_000

    # TLS. With neither file set, the launcher creates and reuses a self-signed
    # certificate that the control plane pins during pairing.
    tls_cert_file: str = ""
    tls_key_file: str = ""
    tls_state_dir: str = ""
    tls_san: str = ""
    allow_insecure_http: bool = False

    # Unpaged list endpoints fail explicitly beyond this size instead of truncating.
    max_unpaged_results: int = Field(default=5000, ge=100, le=50_000)
    health_cache_seconds: int = Field(default=60, ge=0, le=3600)
    # GPO backups may only be written below this directory.
    gpo_backup_root: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def token_initialized(self) -> bool:
        return self.agent_token not in UNINITIALIZED_TOKENS and len(self.agent_token) >= 32

    @property
    def effective_gpo_backup_root(self) -> str:
        if self.gpo_backup_root.strip():
            return self.gpo_backup_root.strip()
        program_data = os.environ.get("ProgramData") or r"C:\ProgramData"
        return str(Path(program_data) / "RSATFull" / "GpoBackups")


settings = Settings()
