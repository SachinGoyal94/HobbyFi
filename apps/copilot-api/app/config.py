from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
