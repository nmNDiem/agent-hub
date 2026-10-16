from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

KnowledgeBaseKind = Literal["shop", "faq", "policy", "general"]
KnowledgeDocumentKind = Literal["profile", "faq", "policy", "size_guidance", "document"]
IngestionStatus = Literal[
    "uploading",
    "awaiting_profile",
    "queued",
    "processing",
    "retry_scheduled",
    "succeeded",
    "failed",
    "cancelled",
]
FreshnessState = Literal["unknown", "current", "due_soon", "overdue"]
RecoveryState = Literal[
    "in_progress",
    "ready",
    "retryable_failure",
    "permanent_failure",
    "attempts_exhausted",
    "lease_expired",
    "projection_drift",
    "cancelled",
]


def cleaned_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Value cannot be blank")
    return cleaned


class KnowledgeBaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    kind: KnowledgeBaseKind = "general"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return cleaned_text(value)


class KnowledgeBaseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    kind: KnowledgeBaseKind | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return cleaned_text(value) if value is not None else None


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    kind: KnowledgeBaseKind
    status: Literal["active", "archived"]
    active_embedding_profile_id: int | None
    target_embedding_profile_id: int | None
    document_count: int
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse]
    next_cursor: str | None


class AgentKnowledgeBasesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_base_ids: list[int] = Field(max_length=100)

    @field_validator("knowledge_base_ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        if any(item < 1 for item in value):
            raise ValueError("Knowledge base IDs must be positive")
        return sorted(set(value))


class AgentKnowledgeBasesResponse(BaseModel):
    public_agent_id: UUID
    knowledge_base_ids: list[int]


class ManualKnowledgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    kind: Literal["profile", "faq", "policy", "size_guidance"]
    content: str = Field(min_length=1)

    @field_validator("title", "content")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return cleaned_text(value)


class ManualKnowledgeReplacementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        return cleaned_text(value)


class KnowledgeReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_due_at: datetime | None = None

    @field_validator("review_due_at")
    @classmethod
    def validate_review_due_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Review due time must include a timezone")
        return value.astimezone(UTC)


class KnowledgeRecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return cleaned_text(value)


class IngestionJobResponse(BaseModel):
    id: int
    document_id: int
    document_version_id: int
    target_generation_id: int | None
    status: IngestionStatus
    attempts: int
    last_error_code: str | None
    retryable: bool
    scheduled_at: datetime
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    recovery_state: RecoveryState
    active_generation_changed: bool = False


class KnowledgeDocumentResponse(BaseModel):
    id: int
    knowledge_base_id: int
    title: str
    kind: KnowledgeDocumentKind
    status: Literal["active", "deleted"]
    source_kind: Literal["manual", "file"]
    latest_version_id: int
    version_no: int
    mime_type: str
    byte_size: int
    active_generation_id: int | None
    active_version_no: int | None
    reviewed_at: datetime | None
    review_due_at: datetime | None
    reviewed_by_user_id: UUID | None
    freshness_state: FreshnessState
    ingestion_job: IngestionJobResponse
    active_generation_changed: bool = False
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentResponse]
    next_cursor: str | None


class KnowledgeVersionResponse(BaseModel):
    id: int
    version_no: int
    source_kind: Literal["manual", "file"]
    mime_type: str
    byte_size: int
    content_sha256: str
    created_by_user_id: UUID
    created_at: datetime
    reviewed_at: datetime | None
    review_due_at: datetime | None
    reviewed_by_user_id: UUID | None
    freshness_state: FreshnessState
    generation_id: int | None
    generation_status: Literal["building", "ready", "failed", "revoked"] | None
    generation_failure_code: str | None
    is_active: bool
    ingestion_job: IngestionJobResponse | None


class KnowledgeVersionListResponse(BaseModel):
    items: list[KnowledgeVersionResponse]
    next_cursor: str | None


class KnowledgeDiagnosticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=10)
    knowledge_base_ids: list[int] | None = Field(default=None, min_length=1, max_length=20)
    agent_public_id: UUID | None = None

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        return cleaned_text(value)

    @field_validator("knowledge_base_ids")
    @classmethod
    def validate_base_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(item < 1 for item in value):
            raise ValueError("Knowledge base IDs must be positive")
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_target(self) -> "KnowledgeDiagnosticRequest":
        if (self.knowledge_base_ids is None) == (self.agent_public_id is None):
            raise ValueError("Exactly one diagnostic target is required")
        return self


class KnowledgeDiagnosticSource(BaseModel):
    knowledge_base_id: int
    document_id: int
    document_title: str
    version_id: int
    version_no: int
    generation_id: int


class KnowledgeDiagnosticHit(BaseModel):
    rank: int
    knowledge_base_id: int
    document_id: int
    document_title: str
    chunk_id: int
    source_locator: str
    embedding_profile_id: int
    similarity_score: float
    snippet: str


class KnowledgeDiagnosticResponse(BaseModel):
    status: Literal["completed", "dependency_unavailable"]
    target_type: Literal["knowledge_bases", "agent"]
    resolved_knowledge_base_ids: list[int]
    active_sources: list[KnowledgeDiagnosticSource]
    hits: list[KnowledgeDiagnosticHit]
    raw_hit_count: int
    discarded_hit_count: int
    reason_codes: list[str]
