from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from agent_hub_api.telemetry.schemas import UsageSummaryResponse
from agent_hub_api.widget.public_schemas import PublicAvailabilitySummary, PublicPriceSummary


class ConversationSummary(BaseModel):
    public_id: UUID
    channel: Literal["web"] = "web"
    agent_public_id: UUID
    agent_name: str
    started_at: datetime
    last_message_at: datetime
    message_count: int
    last_visitor_preview: str | None


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
    role: Literal["user", "assistant"]
    text: str
    status: Literal["pending", "completed", "failed", "cancelled"]
    created_at: datetime
    completed_at: datetime | None
    attachment: ConversationAttachment | None
    products: list[ConversationProductEvidence]
    sources: list[ConversationSourceEvidence]


class ConversationDetailResponse(BaseModel):
    conversation: ConversationSummary
    messages: list[ConversationMessageResponse]
    retention_until: datetime


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
