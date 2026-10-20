from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

AgentStatus = Literal["draft", "published", "paused"]
AgentIcon = Literal[
    "message-circle",
    "bot",
    "headphones",
    "sparkles",
    "shopping-bag",
    "calendar-days",
    "briefcase-business",
    "heart-handshake",
]
DEFAULT_AGENT_ICON: AgentIcon = "message-circle"
DEFAULT_AGENT_COLOR = "#0E8A8C"


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    icon: AgentIcon = DEFAULT_AGENT_ICON
    color: str = Field(default=DEFAULT_AGENT_COLOR, pattern=r"^#[0-9A-Fa-f]{6}$")
    greeting: str | None = Field(default=None, max_length=2_000)
    safe_instructions: str | None = Field(default=None, max_length=10_000)
    default_locale: str = Field(default="vi", min_length=2, max_length=16)
    follow_up_action_enabled: bool = False

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Agent name cannot be blank")
        return cleaned

    @field_validator("greeting", "safe_instructions")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("default_locale")
    @classmethod
    def clean_locale(cls, value: str) -> str:
        normalized = value.strip().replace("_", "-")
        if not 2 <= len(normalized) <= 16 or any(
            not part.isascii() or not part.isalnum() for part in normalized.split("-")
        ):
            raise ValueError("Locale must contain only alphanumeric subtags")
        return normalized

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value.upper()


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    icon: AgentIcon | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    greeting: str | None = Field(default=None, max_length=2_000)
    safe_instructions: str | None = Field(default=None, max_length=10_000)
    default_locale: str | None = Field(default=None, min_length=2, max_length=16)
    follow_up_action_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Agent name cannot be blank")
        return cleaned

    @field_validator("greeting", "safe_instructions")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("default_locale")
    @classmethod
    def clean_locale(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().replace("_", "-")
        if not 2 <= len(normalized) <= 16 or any(
            not part.isascii() or not part.isalnum() for part in normalized.split("-")
        ):
            raise ValueError("Locale must contain only alphanumeric subtags")
        return normalized

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class AgentCatalogScopeRequest(BaseModel):
    """Null selects every active entity; an empty list explicitly selects none."""

    model_config = ConfigDict(extra="forbid")

    location_ids: list[int] | None = None
    collection_ids: list[int] | None = None

    @field_validator("location_ids", "collection_ids")
    @classmethod
    def validate_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(item < 1 for item in value):
            raise ValueError("Scope IDs must be positive integers")
        return sorted(set(value))


class AgentCatalogScopeResponse(BaseModel):
    location_ids: list[int] | None
    collection_ids: list[int] | None


class AgentResponse(BaseModel):
    public_id: UUID
    name: str
    icon: AgentIcon
    color: str
    greeting: str | None
    safe_instructions: str | None
    default_locale: str
    status: AgentStatus
    follow_up_action_enabled: bool
    catalog_scope: AgentCatalogScopeResponse
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    items: list[AgentResponse]
