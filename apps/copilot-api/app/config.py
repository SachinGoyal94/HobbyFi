from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_async_database_url(url: str) -> str:
    """Normalize provider URLs for SQLAlchemy async engines.

    Aiven and many hosts emit ``postgres://`` or ``postgresql://`` with
    libpq ``sslmode=``. Async SQLAlchemy needs ``postgresql+asyncpg://``
    and asyncpg's ``ssl=`` query param.
    """
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    # asyncpg does not accept sslmode= (libpq); map common values
    url = url.replace("sslmode=require", "ssl=require")
    url = url.replace("sslmode=prefer", "ssl=prefer")
    url = url.replace("sslmode=verify-full", "ssl=verify-full")
    return url


def to_sync_database_url(url: str) -> str:
    """Convert an async (or provider) URL to a sync SQLAlchemy URL."""
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    # psycopg2 expects sslmode=
    url = url.replace("ssl=require", "sslmode=require")
    url = url.replace("ssl=prefer", "sslmode=prefer")
    url = url.replace("ssl=verify-full", "sslmode=verify-full")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "HobbyFi Vendor Copilot API"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    database_url: str = "sqlite+aiosqlite:///./copilot_mock.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 2048

    proposal_ttl_minutes: int = 30

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_async_database_url(value)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
