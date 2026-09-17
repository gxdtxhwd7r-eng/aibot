from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    openai_timeout_seconds: float = Field(default=45, gt=0)
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    database_path: str = "data/amk_ai.sqlite3"
    max_upload_mb: int = Field(default=15, ge=1, le=100)
    ai_concurrency: int = Field(default=3, ge=1, le=10)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
