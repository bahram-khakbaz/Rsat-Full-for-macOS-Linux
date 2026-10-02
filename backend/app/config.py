from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "RSAT Full Admin Center"
    environment: str = "development"
    database_url: str = "sqlite:///./rsat.db"
    jwt_secret: str = "change-me"
    jwt_exp_minutes: int = 480
    admin_username: str = "admin"
    admin_password: str = "change-me"
    demo_mode: bool = True
    worker_url: str = ""
    worker_token: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

settings = Settings()
