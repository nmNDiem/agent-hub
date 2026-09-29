from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    """Application defaults with server-side environment overrides."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "AgentHub API"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    database_url: str | None = Field(default=None, repr=False)
    jwt_signing_key: str | None = Field(
        default=None,
        repr=False,
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
    supabase_url: str | None = None
    supabase_service_role_key: str | None = Field(
        default=None,
        repr=False,
    )
    storage_private_bucket: str = "agent-hub-private"
    catalog_image_max_bytes: int = 5 * 1024 * 1024
    catalog_image_max_pixels: int = 20_000_000
    catalog_import_max_bytes: int = 10 * 1024 * 1024
    catalog_import_max_rows: int = 20_000
    catalog_import_max_columns: int = 200
    catalog_import_max_sheets: int = 20
    # Legacy names retained for the compatibility endpoints.
    catalog_csv_max_bytes: int = 10 * 1024 * 1024
    catalog_csv_max_rows: int = 20_000
    storage_signed_url_seconds: int = 300
    catalog_import_lease_seconds: int = 300
    knowledge_document_max_bytes: int = 10 * 1024 * 1024
    knowledge_manual_max_chars: int = 100_000
    knowledge_pdf_max_pages: int = 200
    knowledge_extracted_max_chars: int = 1_000_000
    knowledge_max_chunks_per_generation: int = 1_000
    knowledge_chunk_size: int = 1_200
    knowledge_chunk_overlap: int = 150
    knowledge_workspace_storage_bytes: int = 100 * 1024 * 1024
    knowledge_workspace_max_documents: int = 100
    knowledge_workspace_max_chunks: int = 20_000
    knowledge_upload_window_minutes: int = 10
    knowledge_uploads_per_window: int = 10
    knowledge_workspace_active_jobs: int = 2
    knowledge_job_lease_seconds: int = 120
    knowledge_job_heartbeat_seconds: int = 30
    knowledge_job_max_attempts: int = 5
    knowledge_retry_base_seconds: int = 5
    knowledge_retry_max_seconds: int = 900
    knowledge_parser_wall_seconds: int = 30
    knowledge_parser_cpu_seconds: int = 20
    knowledge_parser_memory_bytes: int = 512 * 1024 * 1024
    knowledge_parser_output_bytes: int = 4 * 1024 * 1024

    @model_validator(mode="after")
    def validate_knowledge_limits(self) -> "Settings":
        if self.knowledge_chunk_overlap >= self.knowledge_chunk_size:
            raise ValueError("Knowledge chunk overlap must be smaller than chunk size")
        if self.knowledge_job_heartbeat_seconds >= self.knowledge_job_lease_seconds:
            raise ValueError("Knowledge heartbeat must be shorter than the job lease")
        return self

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
