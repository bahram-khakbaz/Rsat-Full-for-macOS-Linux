from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    agent_token: str = "change-me"
    listen_host: str = "0.0.0.0"
    listen_port: int = 8765
    powershell_exe: str = "powershell.exe"
    max_output_bytes: int = 4_000_000
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
