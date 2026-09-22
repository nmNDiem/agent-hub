from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
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
    jwt_signing_key: str | None = Field(
        default=None,
        repr=False,
        validation_alias=AliasChoices("AGENT_HUB_JWT_SIGNING_KEY", "JWT_SIGNING_KEY"),
    )
    jwt_issuer: str = "agent-hub-api"
    jwt_audience: str = "agent-hub-dashboard"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cookie_secure: bool = False
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    )
    email_delivery_enabled: bool = False
    supabase_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL", "AGENT_HUB_SUPABASE_URL"),
    )
    supabase_service_role_key: str | None = Field(
        default=None,
        repr=False,
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY", "AGENT_HUB_SUPABASE_SERVICE_ROLE_KEY"
        ),
    )
    storage_private_bucket: str = "agent-hub-private"
    catalog_image_max_bytes: int = 5 * 1024 * 1024
    catalog_image_max_pixels: int = 20_000_000
    catalog_csv_max_bytes: int = 2 * 1024 * 1024
    catalog_csv_max_rows: int = 5_000
    storage_signed_url_seconds: int = 300
    catalog_import_lease_seconds: int = 300

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str | None) -> str | None:
        return normalize_database_url(value) if value is not None else None

    @field_validator("jwt_signing_key")
    @classmethod
    def validate_jwt_signing_key(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode()) < 32:
            raise ValueError("JWT signing key must contain at least 32 bytes")
        return value

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.app_env in {"staging", "production"}:
            if self.jwt_signing_key is None:
                raise ValueError("JWT signing key is required outside local/test")
            if not self.cookie_secure:
                raise ValueError("Secure cookies are required outside local/test")
            if not self.allowed_origins or any(
                not origin.startswith("https://") for origin in self.allowed_origins
            ):
                raise ValueError("HTTPS allowed origins are required outside local/test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
