from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from argon2 import extract_parameters
from argon2.exceptions import InvalidHashError
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminSettings(BaseSettings):
    """Configuration de sécurité chargée exclusivement depuis l'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = (
        "postgresql+asyncpg://cv_generator:cv_generator@localhost:5432/cv_generator"
    )
    admin_username: str | None = None
    admin_password_hash: str | None = None
    admin_session_secret: str | None = None
    admin_session_ttl_seconds: int = Field(default=3600, ge=300, le=86400)
    admin_session_cookie_name: str = "cv_generator_admin_session"
    admin_csrf_cookie_name: str = "cv_generator_admin_csrf"
    admin_cookie_secure: bool = False
    admin_base_url: str = "http://127.0.0.1:8001"
    admin_timezone: str = "Pacific/Noumea"
    admin_login_window_seconds: int = Field(default=900, ge=60, le=86400)
    admin_login_max_attempts: int = Field(default=5, ge=2, le=100)
    admin_trusted_proxy_ips: str = ""

    @field_validator("admin_username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @property
    def trusted_proxy_ips(self) -> frozenset[str]:
        return frozenset(
            item.strip()
            for item in self.admin_trusted_proxy_ips.split(",")
            if item.strip()
        )

    @property
    def timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.admin_timezone)
        except ZoneInfoNotFoundError as error:
            raise RuntimeError(
                f"ADMIN_TIMEZONE est inconnu : {self.admin_timezone}"
            ) from error

    @property
    def timezone_label(self) -> str:
        if self.admin_timezone == "Pacific/Noumea":
            return "Heure de Nouméa"
        return f"Heure locale ({self.admin_timezone})"

    def validate_security(self) -> None:
        _ = self.timezone
        missing = []
        if not self.admin_username:
            missing.append("ADMIN_USERNAME")
        if not self.admin_password_hash:
            missing.append("ADMIN_PASSWORD_HASH")
        if not self.admin_session_secret or len(self.admin_session_secret) < 32:
            missing.append("ADMIN_SESSION_SECRET (32 caractères minimum)")
        if missing:
            raise RuntimeError(
                "Configuration administrateur absente ou invalide : "
                + ", ".join(missing)
            )
        try:
            parameters = extract_parameters(self.admin_password_hash or "")
        except InvalidHashError as error:
            raise RuntimeError(
                "ADMIN_PASSWORD_HASH n'est pas un hash Argon2 valide"
            ) from error
        if parameters.type.name.lower() != "id":
            raise RuntimeError("ADMIN_PASSWORD_HASH doit utiliser Argon2id")
        if self.app_env == "production":
            if not self.admin_cookie_secure:
                raise RuntimeError("ADMIN_COOKIE_SECURE doit être activé en production")
            parsed_base_url = urlsplit(self.admin_base_url)
            try:
                port = parsed_base_url.port
            except ValueError as error:
                raise RuntimeError("ADMIN_BASE_URL est invalide") from error
            if (
                parsed_base_url.scheme != "https"
                or not parsed_base_url.hostname
                or parsed_base_url.username is not None
                or parsed_base_url.password is not None
                or parsed_base_url.query
                or parsed_base_url.fragment
                or port is not None
                and not 1 <= port <= 65535
            ):
                raise RuntimeError(
                    "ADMIN_BASE_URL doit être une URL HTTPS valide en production"
                )


@lru_cache
def get_settings() -> AdminSettings:
    return AdminSettings()
