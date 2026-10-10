from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration du service chargée depuis l'environnement et `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = (
        "postgresql+asyncpg://cv_generator:cv_generator@localhost:5432/cv_generator"
    )

    opt_avp_base_url: str = "https://opt-nc.github.io/odata-avps"

    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = Field(default=120, gt=0)

    worker_poll_interval_seconds: float = Field(default=1, gt=0)
    worker_stale_job_timeout_seconds: float = Field(default=600, gt=0)

    libreoffice_executable: str = "libreoffice"
    pdf_conversion_timeout_seconds: float = Field(default=60, gt=0)
    pdf_conversion_max_concurrent: int = Field(default=2, ge=1, le=16)


@lru_cache
def get_settings() -> Settings:
    return Settings()
