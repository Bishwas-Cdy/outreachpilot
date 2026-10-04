from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./outreachpilot.db"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    value_proposition: str = (
        "We help revenue teams automate evidence-based account research and qualification "
        "so reps can spend more time in conversations."
    )
    sender_name: str = "Alex"
    delivery_mode: Literal["mock", "webhook"] = "mock"
    outbound_webhook_url: str | None = None
    webhook_auto_process: bool = False
    scrape_timeout_seconds: float = Field(default=10, gt=0, le=30)
    scrape_max_bytes: int = Field(default=1_000_000, gt=0, le=5_000_000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
