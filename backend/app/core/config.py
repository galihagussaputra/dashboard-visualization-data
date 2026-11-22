from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "IDX Financial Intelligence"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://finance:change-me-locally@db:5432/idx_finance"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    idx_base_url: str = "https://www.idx.id"
    idx_request_delay_seconds: float = 1.0
    idx_user_agent: str = "IDX-Financial-Intelligence/0.1 (local-development)"
    session_ttl_minutes: int = 480

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
