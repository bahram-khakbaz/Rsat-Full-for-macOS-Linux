from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values shipped in examples/defaults. They must never protect a real deployment.
PLACEHOLDER_SECRETS = frozenset(
    {
        "",
        "change-me",
        "replace-with-a-long-random-secret",
        "replace-with-a-strong-password",
        "replace-with-a-separate-random-encryption-key",
    }
)


class Settings(BaseSettings):
    app_name: str = "RSAT Full Admin Center"
    environment: str = "development"
    database_url: str = "sqlite:///./rsat.db"
    jwt_secret: str = "change-me"  # noqa: S105 - placeholder, rejected in production
    jwt_exp_minutes: int = Field(default=480, ge=5, le=1440)
    # Dedicated key for stored credentials. When empty, the legacy key derived
    # from JWT_SECRET is used so existing installations keep working.
    encryption_key: str = ""
    # Comma-separated former ENCRYPTION_KEY values, accepted for decryption only.
    encryption_key_previous: str = ""
    admin_username: str = "admin"
    admin_password: str = "change-me"  # noqa: S105 - placeholder, rejected in production
    demo_mode: bool = True
    worker_url: str = ""
    worker_token: str = ""
    # Plain-HTTP worker traffic exposes the worker credential and new passwords.
    allow_insecure_worker: bool = False
    vault_credential_dir: str = ""
    vault_max_age_seconds: int = Field(default=180, ge=30, le=3600)
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    login_max_failures: int = Field(default=5, ge=1, le=100)
    login_lockout_seconds: int = Field(default=900, ge=10, le=86400)
    # None: mark the session cookie Secure whenever the request arrived over HTTPS.
    cookie_secure: bool | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    def placeholder_secrets(self) -> list[str]:
        """Settings still holding example values; fatal in production."""
        problems = []
        if self.jwt_secret in PLACEHOLDER_SECRETS or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET (use at least 32 random characters)")
        if self.admin_password in PLACEHOLDER_SECRETS:
            problems.append("ADMIN_PASSWORD (replace the example value)")
        if self.encryption_key and (
            self.encryption_key in PLACEHOLDER_SECRETS or len(self.encryption_key) < 32
        ):
            problems.append("ENCRYPTION_KEY (use at least 32 random characters)")
        return problems

    def weak_settings(self) -> list[str]:
        """Settings that work but deserve attention; reported as warnings."""
        warnings = []
        if self.admin_password not in PLACEHOLDER_SECRETS and len(self.admin_password) < 12:
            warnings.append("ADMIN_PASSWORD is shorter than 12 characters")
        if not self.encryption_key:
            warnings.append(
                "ENCRYPTION_KEY is not set; stored credentials are protected by a key "
                "derived from JWT_SECRET"
            )
        if self.allow_insecure_worker:
            warnings.append("ALLOW_INSECURE_WORKER permits unencrypted worker traffic")
        return warnings


settings = Settings()
