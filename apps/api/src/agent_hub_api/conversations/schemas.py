from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_hub_api.telemetry.schemas import UsageSummaryResponse
from agent_hub_api.widget.public_schemas import PublicAvailabilitySummary, PublicPriceSummary


class ConversationSummary(BaseModel):
    public_id: UUID
    contact_public_id: UUID | None = None
    channel: Literal["web", "facebook", "zalo"]
    agent_public_id: UUID
    agent_name: str
    started_at: datetime
    last_message_at: datetime
    message_count: int
    last_visitor_preview: str | None
    workflow_status: Literal["open", "pending", "resolved"]
    handling_mode: Literal["ai", "human", "paused"]
    state_version: int
    assigned_member_id: int | None
    assigned_member_email: str | None = None
    unread_count: int = 0
    tags: list["ConversationTagResponse"] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]
    next_cursor: str | None


class ConversationAttachment(BaseModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    width: int
    height: int
    byte_size: int
    created_at: datetime


class ConversationProductEvidence(BaseModel):
    name: str
    sku: str | None
    product_url: str | None
    price: PublicPriceSummary
    availability: PublicAvailabilitySummary
    options: dict[str, list[str]]


class ConversationSourceEvidence(BaseModel):
    source_id: str
    title: str
    locator: str


class ConversationMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant", "human"]
    text: str
    status: Literal["pending", "completed", "failed", "cancelled"]
    created_at: datetime
    completed_at: datetime | None
    attachment: ConversationAttachment | None
    products: list[ConversationProductEvidence]
    sources: list[ConversationSourceEvidence]
    delivery: "ConversationDeliveryResponse | None" = None


class ConversationDeliveryResponse(BaseModel):
    state: Literal[
        "queued", "sending", "accepted", "delivered", "failed_retryable", "failed_terminal"
    ]
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    safe_error_code: str | None


class ConversationTagResponse(BaseModel):
    id: int
    name: str


class ConversationNoteResponse(BaseModel):
    id: int
    author_member_id: int
    author_email: str
    body: str
    created_at: datetime


class ConversationFollowUpResponse(BaseModel):
    lead_id: int
    source_channel: Literal["web", "facebook", "zalo"]
    capture_source: Literal["website_form", "agent_action"]
    revision_no: int
    action_status: Literal["succeeded", "failed_retryable", "failed_terminal"] | None = None
    action_replayed: bool = False
    requested_at: datetime
    followup_status: Literal["new", "contacted", "closed"]


class ConversationIntakeResponse(BaseModel):
    submission_public_id: UUID
    purpose: str
    submitted_at: datetime
    qualification_status: Literal["pending_review", "qualified", "not_qualified"]


class InboxMemberResponse(BaseModel):
    id: int
    user_id: UUID
    email: str
    role: Literal["owner", "admin", "member"]


class InboxMemberListResponse(BaseModel):
    items: list[InboxMemberResponse]


class ConversationDetailResponse(BaseModel):
    conversation: ConversationSummary
    messages: list[ConversationMessageResponse]
    retention_until: datetime
    notes: list[ConversationNoteResponse] = Field(default_factory=list)
    follow_up: ConversationFollowUpResponse | None = None
    intake: ConversationIntakeResponse | None = None


class ConversationStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state_version: int = Field(ge=1)
    workflow_status: Literal["open", "pending", "resolved"] | None = None
    handling_mode: Literal["ai", "human", "paused"] | None = None
    assigned_member_id: int | None = None
    clear_assignment: bool = False


class ConversationNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=2_000)

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Note cannot be blank")
        return cleaned


class ConversationTagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=48)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Tag cannot be blank")
        return cleaned


class HumanReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4_000)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Reply cannot be blank")
        return cleaned


class DashboardActivityPoint(BaseModel):
    date: date
    conversations: int


class DashboardLeadSummary(BaseModel):
    name: str | None
    agent_name: str
    followup_status: Literal["new", "contacted", "closed"]
    created_at: datetime


class DashboardResponse(BaseModel):
    days: Literal[7, 30]
    timezone: str
    total_conversations: int
    assistant_messages: int
    active_agents: int
    enabled_web_channels: int
    activity: list[DashboardActivityPoint]
    recent_conversations: list[ConversationSummary]
    recent_leads: list[DashboardLeadSummary]
    usage: UsageSummaryResponse
