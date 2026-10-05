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
    widget_public_base_url: str | None = None
    widget_abuse_hash_key: str | None = Field(default=None, repr=False)
    widget_session_hours: int = 24
    widget_transcript_hours: int = 24
    widget_bootstrap_per_ip_minute: int = 10
    widget_sessions_per_workspace_hour: int = 100
    widget_messages_per_session_hour: int = 30
    widget_messages_per_workspace_hour: int = 300
    email_delivery_enabled: bool = False
    supabase_url: str | None = None
    supabase_service_role_key: str | None = Field(
        default=None,
        repr=False,
    )
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_timeout_seconds: int = 30
    generation_model: str | None = None
    vision_model: str | None = None
    widget_image_max_bytes: int = 5 * 1024 * 1024
    widget_image_max_pixels: int = 20_000_000
    widget_image_session_max_bytes: int = 20 * 1024 * 1024
    widget_image_session_max_uploads: int = 10
    widget_image_unattached_minutes: int = 30
    widget_image_attached_hours: int = 1
    lead_retention_days: int = 30
    lead_export_max_rows: int = 10_000
    retention_sweep_batch_size: int = 100
    retention_rate_window_hours: int = 2
    workspace_monthly_generated_turn_limit: int = 1_000
    agent_runtime_max_question_chars: int = 4_000
    agent_runtime_max_history_turns: int = 8
    agent_runtime_max_history_chars: int = 12_000
    agent_runtime_max_knowledge_chunks: int = 5
    agent_runtime_max_knowledge_chars: int = 12_000
    agent_runtime_max_prompt_chars: int = 60_000
    agent_runtime_max_tool_result_chars: int = 24_000
    agent_runtime_max_output_tokens: int = 800
    agent_runtime_max_total_tokens: int = 8_000
    agent_runtime_max_model_calls: int = 5
    agent_runtime_max_tool_calls: int = 4
    agent_runtime_catalog_result_limit: int = 8
    qdrant_url: str | None = None
    qdrant_api_key: str | None = Field(default=None, repr=False)
    qdrant_collection_prefix: str = "agenthub_knowledge"
    qdrant_timeout_seconds: int = 30
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    embedding_provider_revision: str | None = None
    embedding_pipeline_version: str = "agenthub-rag-v1"
    embedding_distance_metric: Literal["cosine", "dot", "euclid"] = "cosine"
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
    knowledge_embedding_batch_size: int = 64
    knowledge_orphan_grace_seconds: int = 3_600
    knowledge_worker_poll_seconds: int = 2

    @model_validator(mode="after")
    def validate_knowledge_limits(self) -> "Settings":
        positive_fields = (
            "knowledge_document_max_bytes",
            "knowledge_manual_max_chars",
            "knowledge_pdf_max_pages",
            "knowledge_extracted_max_chars",
            "knowledge_max_chunks_per_generation",
            "knowledge_chunk_size",
            "knowledge_workspace_storage_bytes",
            "knowledge_workspace_max_documents",
            "knowledge_workspace_max_chunks",
            "knowledge_upload_window_minutes",
            "knowledge_uploads_per_window",
            "knowledge_workspace_active_jobs",
            "knowledge_job_lease_seconds",
            "knowledge_job_heartbeat_seconds",
            "knowledge_job_max_attempts",
            "knowledge_retry_base_seconds",
            "knowledge_retry_max_seconds",
            "knowledge_parser_wall_seconds",
            "knowledge_parser_cpu_seconds",
            "knowledge_parser_memory_bytes",
            "knowledge_parser_output_bytes",
            "knowledge_embedding_batch_size",
            "knowledge_orphan_grace_seconds",
            "knowledge_worker_poll_seconds",
            "openai_timeout_seconds",
            "agent_runtime_max_question_chars",
            "agent_runtime_max_history_turns",
            "agent_runtime_max_history_chars",
            "agent_runtime_max_knowledge_chunks",
            "agent_runtime_max_knowledge_chars",
            "agent_runtime_max_prompt_chars",
            "agent_runtime_max_tool_result_chars",
            "agent_runtime_max_output_tokens",
            "agent_runtime_max_total_tokens",
            "agent_runtime_max_model_calls",
            "agent_runtime_max_tool_calls",
            "agent_runtime_catalog_result_limit",
            "qdrant_timeout_seconds",
            "widget_session_hours",
            "widget_transcript_hours",
            "widget_bootstrap_per_ip_minute",
            "widget_sessions_per_workspace_hour",
            "widget_messages_per_session_hour",
            "widget_messages_per_workspace_hour",
            "widget_image_max_bytes",
            "widget_image_max_pixels",
            "widget_image_session_max_bytes",
            "widget_image_session_max_uploads",
            "widget_image_unattached_minutes",
            "widget_image_attached_hours",
            "lead_retention_days",
            "lead_export_max_rows",
            "retention_sweep_batch_size",
            "retention_rate_window_hours",
            "workspace_monthly_generated_turn_limit",
        )
        if any(getattr(self, field_name) < 1 for field_name in positive_fields):
            raise ValueError("Configured limits must be positive")
        if self.knowledge_chunk_overlap < 0:
            raise ValueError("Knowledge chunk overlap cannot be negative")
        if self.knowledge_chunk_overlap >= self.knowledge_chunk_size:
            raise ValueError("Knowledge chunk overlap must be smaller than chunk size")
        if self.knowledge_job_heartbeat_seconds >= self.knowledge_job_lease_seconds:
            raise ValueError("Knowledge heartbeat must be shorter than the job lease")
        if self.knowledge_retry_base_seconds > self.knowledge_retry_max_seconds:
            raise ValueError("Knowledge retry base cannot exceed its maximum")
        if self.agent_runtime_max_knowledge_chunks > 20:
            raise ValueError("Agent knowledge retrieval cannot exceed 20 chunks")
        if self.agent_runtime_catalog_result_limit > 100:
            raise ValueError("Agent catalog result limit cannot exceed 100 products")
        if self.agent_runtime_max_output_tokens >= self.agent_runtime_max_total_tokens:
            raise ValueError("Agent output tokens must be smaller than its total token budget")
        return self

    @field_validator(
        "openai_api_key",
        "qdrant_api_key",
        "qdrant_url",
        "embedding_model",
        "embedding_provider_revision",
        "generation_model",
        "vision_model",
        "widget_public_base_url",
        "widget_abuse_hash_key",
        mode="before",
    )
    @classmethod
    def normalize_optional_provider_setting(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned or cleaned.startswith("REPLACE_") or "<cluster>" in cleaned:
                return None
            return cleaned
        return value

    @field_validator("widget_public_base_url")
    @classmethod
    def validate_widget_public_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Widget public base URL must be an HTTP(S) origin")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Widget public base URL cannot contain credentials or query data")
        if parsed.path not in {"", "/"}:
            raise ValueError("Widget public base URL must not contain a path")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("HTTP widget public base URL is limited to local loopback")
        return value.rstrip("/")

    @field_validator("widget_abuse_hash_key")
    @classmethod
    def validate_widget_abuse_hash_key(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode()) < 32:
            raise ValueError("Widget abuse hash key must contain at least 32 bytes")
        return value

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def normalize_embedding_dimensions(cls, value: object) -> object:
        if isinstance(value, str) and (not value.strip() or value.startswith("REPLACE_")):
            return None
        return value

    @field_validator("qdrant_collection_prefix")
    @classmethod
    def validate_qdrant_collection_prefix(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 160:
            raise ValueError("Qdrant collection prefix must contain 1-160 characters")
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        if any(character not in allowed for character in cleaned):
            raise ValueError("Qdrant collection prefix contains unsupported characters")
        return cleaned

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
