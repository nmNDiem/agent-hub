from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContactTagResponse(BaseModel):
    id: int
    name: str


class ContactSummary(BaseModel):
    public_id: UUID
    display_name: str | None
    lifecycle_state: Literal["active", "expired", "merged"]
    state_version: int
    assigned_member_id: int | None
    assigned_member_email: str | None
    channels: list[Literal["website", "facebook", "zalo"]] = Field(default_factory=list)
    tags: list[ContactTagResponse] = Field(default_factory=list)
    retention_until: datetime
    updated_at: datetime


class ContactListResponse(BaseModel):
    items: list[ContactSummary]
    next_cursor: str | None


class ContactIdentityResponse(BaseModel):
    id: int
    provider: Literal["website", "facebook", "zalo"]
    identity_type: Literal["email", "phone", "channel"]
    value: str | None
    verification_state: Literal["consented", "provider_asserted"]
    consent_at: datetime | None
    consent_text_version: str | None
    retention_until: datetime


class ContactNoteResponse(BaseModel):
    id: int
    author_member_id: int
    author_email: str
    body: str
    created_at: datetime


class ContactTimelineItem(BaseModel):
    key: str
    kind: Literal["conversation", "lead", "note", "state", "merge"]
    occurred_at: datetime
    title: str
    detail: str | None = None
    conversation_public_id: UUID | None = None
    lead_id: int | None = None
    source_channel: Literal["web", "facebook", "zalo"] | None = None
    capture_source: Literal["website_form", "agent_action"] | None = None
    revision_no: int | None = None
    action_status: Literal["succeeded", "failed_retryable", "failed_terminal"] | None = None
    action_replayed: bool = False
    intake_purpose: str | None = None
    qualification_status: Literal[
        "pending_review", "qualified", "not_qualified"
    ] | None = None


class ContactDuplicateCandidate(BaseModel):
    public_id: UUID
    display_name: str | None
    matching_identity_types: list[Literal["email", "phone"]]


class ContactActiveMerge(BaseModel):
    id: int
    source_public_id: UUID
    target_public_id: UUID
    reason: str
    created_at: datetime


class ContactDetailResponse(BaseModel):
    contact: ContactSummary
    canonical_public_id: UUID | None = None
    identities: list[ContactIdentityResponse] = Field(default_factory=list)
    notes: list[ContactNoteResponse] = Field(default_factory=list)
    timeline: list[ContactTimelineItem] = Field(default_factory=list)
    duplicate_candidates: list[ContactDuplicateCandidate] = Field(default_factory=list)
    active_merges: list[ContactActiveMerge] = Field(default_factory=list)


class ContactStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, max_length=120)
    update_display_name: bool = False
    assigned_member_id: int | None = None
    clear_assignment: bool = False

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split()) or None

    @model_validator(mode="after")
    def validate_assignment(self) -> "ContactStateRequest":
        if self.assigned_member_id is not None and self.clear_assignment:
            raise ValueError("Cannot assign and clear assignment together")
        return self


class ContactNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=2_000)

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Note cannot be blank")
        return cleaned


class ContactTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=48)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Tag cannot be blank")
        return cleaned


class ContactMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_public_id: UUID
    source_state_version: int = Field(ge=1)
    target_state_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=240)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 3:
            raise ValueError("Merge reason is too short")
        return cleaned
