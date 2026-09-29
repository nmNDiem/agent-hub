from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class KnowledgeDocumentResponse(BaseModel):
    id: int
    knowledge_base_id: int
    title: str
    kind: KnowledgeDocumentKind
    status: Literal["active", "deleted"]
    source_kind: Literal["manual", "file"]
    version_no: int
    mime_type: str
    byte_size: int
    active_generation_id: int | None
    ingestion_job: IngestionJobResponse
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentResponse]
    next_cursor: str | None
