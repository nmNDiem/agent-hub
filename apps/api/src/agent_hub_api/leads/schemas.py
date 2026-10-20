from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

LeadStatus = Literal["new", "contacted", "closed"]
QualificationStatus = Literal["pending_review", "qualified", "not_qualified"]


def contact_consent_version(retention_days: int) -> str:
    return f"vi-VN:contact-v1:{retention_days}d"


def contact_consent_text(retention_days: int) -> str:
    return (
        "Tôi đồng ý để cửa hàng dùng thông tin này liên hệ lại "
        f"và lưu tối đa {retention_days} ngày."
    )


CONTACT_CONSENT_VERSION = contact_consent_version(30)


class LeadCaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    consent_given: Literal[True]
    consent_text_version: str = Field(min_length=1, max_length=80)

    @field_validator("name", "phone", mode="before")
    @classmethod
    def trim_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = set("+0123456789()-. ")
        digits = sum(character.isdigit() for character in value)
        if any(character not in allowed for character in value) or not 7 <= digits <= 15:
            raise ValueError("Phone number is invalid")
        return value

    @model_validator(mode="after")
    def require_contact(self) -> "LeadCaptureRequest":
        if self.email is None and self.phone is None:
            raise ValueError("Email or phone is required")
        return self


class LeadCaptureResponse(BaseModel):
    status: Literal["received"] = "received"
    followup_status: LeadStatus
    retention_until: datetime


class LeadIntakeSummary(BaseModel):
    public_id: UUID
    purpose: str
    submitted_at: datetime
    action_status: Literal["succeeded", "failed_retryable", "failed_terminal"]
    action_replayed: bool = False


class LeadResponse(BaseModel):
    id: int
    conversation_public_id: UUID
    agent_public_id: UUID
    agent_name: str
    name: str | None
    email: str | None
    phone: str | None
    source_channel: Literal["web", "facebook", "zalo"]
    capture_source: Literal["website_form", "agent_action"]
    revision_no: int
    action_status: Literal["succeeded", "failed_retryable", "failed_terminal"] | None = None
    action_replayed: bool = False
    consent_at: datetime | None
    consent_text_version: str | None
    followup_status: LeadStatus
    qualification_status: QualificationStatus | None
    qualification_version: int
    qualification_reason: str | None
    qualification_updated_at: datetime | None
    intake: LeadIntakeSummary | None = None
    retention_until: datetime
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    next_cursor: str | None


class LeadStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    followup_status: LeadStatus


class LeadIntakeAnswer(BaseModel):
    field_key: UUID
    label: str
    value: str | list[str]


class LeadIntakeDetail(LeadIntakeSummary):
    disclosure_version: str
    answers: list[LeadIntakeAnswer]


class LeadDetailResponse(BaseModel):
    lead: LeadResponse
    intake: LeadIntakeDetail | None


class LeadQualificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualification_status: Literal["qualified", "not_qualified"]
    qualification_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            return cleaned or None
        return value
