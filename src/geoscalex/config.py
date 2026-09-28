from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEOSCALEX_", env_file=".env", extra="ignore")

    data_dir: Path = Path(".geoscalex")
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://127.0.0.1:5173"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "geoscalex.sqlite3"


settings = Settings()
