import json
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
IntakeFieldType = Literal[
    "short_text", "long_text", "email", "phone", "single_choice", "multiple_choice", "date"
]
IntakeFieldSemantic = Literal[
    "name",
    "email",
    "phone",
    "service_category",
    "service_area",
    "preferred_date",
    "preference",
    "context",
]

_INTAKE_KIND_BY_SEMANTIC: dict[str, frozenset[str]] = {
    "name": frozenset({"short_text"}),
    "email": frozenset({"email"}),
    "phone": frozenset({"phone"}),
    "service_category": frozenset({"single_choice", "multiple_choice"}),
    "service_area": frozenset({"short_text"}),
    "preferred_date": frozenset({"date"}),
    "preference": frozenset({"short_text", "long_text", "single_choice", "multiple_choice"}),
    "context": frozenset({"short_text", "long_text"}),
}
_PROHIBITED_INTAKE_PATTERN = re.compile(
    r"\b(password|passcode|otp|pin|cvv|credit card|bank account|passport|government id|"
    r"biometric|genetic|medical record|health record|precise location|gps coordinate|"
    r"race|ethnicity|religion|political opinion|trade union|criminal record|sexual orientation|"
    r"mật khẩu|mã otp|mã pin|thẻ tín dụng|tài khoản ngân hàng|căn cước|cccd|cmnd|"
    r"hộ chiếu|sinh trắc|di truyền|hồ sơ bệnh án|sức khỏe|tọa độ|vị trí chính xác|"
    r"chủng tộc|dân tộc|tôn giáo|quan điểm chính trị|công đoàn|tiền án|xu hướng tính dục)\b",
    re.IGNORECASE,
)


class IntakeChoiceOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: UUID | None = None
    label: str = Field(min_length=1, max_length=80)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if _PROHIBITED_INTAKE_PATTERN.search(cleaned):
            raise ValueError("Intake configuration requests a prohibited data category")
        return cleaned


class IntakeFieldDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: UUID | None = None
    semantic: IntakeFieldSemantic
    label: str = Field(min_length=1, max_length=80)
    help_text: str | None = Field(default=None, max_length=240)
    kind: IntakeFieldType
    required: bool = False
    options: list[IntakeChoiceOption] = Field(default_factory=list, max_length=12)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if _PROHIBITED_INTAKE_PATTERN.search(cleaned):
            raise ValueError("Intake configuration requests a prohibited data category")
        return cleaned

    @field_validator("help_text")
    @classmethod
    def clean_help_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            return None
        if _PROHIBITED_INTAKE_PATTERN.search(cleaned):
            raise ValueError("Intake configuration requests a prohibited data category")
        return cleaned

    @model_validator(mode="after")
    def validate_kind_and_options(self) -> "IntakeFieldDefinition":
        if self.kind not in _INTAKE_KIND_BY_SEMANTIC[self.semantic]:
            raise ValueError("Intake field type does not match its approved semantic")
        choice = self.kind in {"single_choice", "multiple_choice"}
        if choice and len(self.options) < 2:
            raise ValueError("Choice fields require at least two options")
        if not choice and self.options:
            raise ValueError("Only choice fields may define options")
        keys = [option.key for option in self.options if option.key is not None]
        if len(keys) != len(set(keys)):
            raise ValueError("Choice option keys must be unique")
        labels = [option.label.casefold() for option in self.options]
        if len(labels) != len(set(labels)):
            raise ValueError("Choice option labels must be unique")
        return self


class IntakeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(min_length=1, max_length=240)
    disclosure: str = Field(min_length=1, max_length=500)
    disclosure_version: str | None = Field(default=None, max_length=64)
    fields: list[IntakeFieldDefinition] = Field(min_length=1, max_length=12)

    @field_validator("purpose", "disclosure")
    @classmethod
    def clean_copy(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if _PROHIBITED_INTAKE_PATTERN.search(cleaned):
            raise ValueError("Intake configuration requests a prohibited data category")
        return cleaned

    @model_validator(mode="after")
    def validate_definition(self) -> "IntakeDefinition":
        keys = [field.key for field in self.fields if field.key is not None]
        if len(keys) != len(set(keys)):
            raise ValueError("Intake field keys must be unique")
        if not any(field.semantic in {"email", "phone"} for field in self.fields):
            raise ValueError("Intake requires an email or phone field for Website reachability")
        serialized = json.dumps(self.model_dump(mode="json"), ensure_ascii=False)
        if len(serialized) > 12_000:
            raise ValueError("Intake definition is too large")
        return self


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
    intake_action_enabled: bool = False
    intake_definition: IntakeDefinition | None = None

    @model_validator(mode="after")
    def require_intake_definition(self) -> "AgentCreateRequest":
        if self.intake_action_enabled and self.intake_definition is None:
            raise ValueError("Enabled intake requires a definition")
        return self

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
    intake_action_enabled: bool | None = None
    intake_definition: IntakeDefinition | None = None

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
    intake_action_enabled: bool
    intake_definition: IntakeDefinition | None
    catalog_scope: AgentCatalogScopeResponse
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    items: list[AgentResponse]
