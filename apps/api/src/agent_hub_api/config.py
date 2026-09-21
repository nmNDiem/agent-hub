from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    """Select the asyncpg SQLAlchemy dialect without changing URL credentials."""

    if value.startswith("postgresql+asyncpg://"):
        return value
    if value.startswith("postgresql://"):
        return f"postgresql+asyncpg://{value.removeprefix('postgresql://')}"
    if value.startswith("postgres://"):
        return f"postgresql+asyncpg://{value.removeprefix('postgres://')}"
    raise ValueError("Database URL must use a PostgreSQL scheme")


class Settings(BaseSettings):
    """Runtime settings loaded from server-side environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENT_HUB_",
        extra="ignore",
    )

    app_name: str = "AgentHub API"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    database_url: str | None = Field(default=None, repr=False)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str | None) -> str | None:
        return normalize_database_url(value) if value is not None else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
