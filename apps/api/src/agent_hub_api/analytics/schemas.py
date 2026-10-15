from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsActivityPoint(BaseModel):
    date: date
    conversations: int = Field(ge=0)
    inbound_messages: int = Field(ge=0)
    completed_replies: int = Field(ge=0)


class AnalyticsDeliveryOutcomes(BaseModel):
    accepted: int = Field(ge=0)
    delivered: int = Field(ge=0)
    failed_retryable: int = Field(ge=0)
    failed_terminal: int = Field(ge=0)


class AnalyticsBreakdown(BaseModel):
    key: str
    label: str
    conversations: int = Field(ge=0)
    inbound_messages: int = Field(ge=0)
    completed_replies: int = Field(ge=0)
    delivery: AnalyticsDeliveryOutcomes | None


class AnalyticsResponseTiming(BaseModel):
    average_seconds: float | None = Field(default=None, ge=0)
    sample_count: int = Field(ge=0)


class AnalyticsResolution(BaseModel):
    ai_only_resolved: int = Field(ge=0)
    human_handled_resolved: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    handoffs: int = Field(ge=0)


class AnalyticsLeadConversion(BaseModel):
    converted_conversations: int = Field(ge=0)
    eligible_conversations: int = Field(ge=0)
    rate: float | None = Field(default=None, ge=0, le=1)


class AnalyticsProductInterest(BaseModel):
    product_id: int
    product_name: str
    impressions: int = Field(ge=0)
    conversations: int = Field(ge=0)


class AnalyticsAgentOption(BaseModel):
    public_id: UUID
    name: str


class AnalyticsSummary(BaseModel):
    conversations: int = Field(ge=0)
    inbound_messages: int = Field(ge=0)
    completed_replies: int = Field(ge=0)
    failed_replies: int = Field(ge=0)


class OperationalAnalyticsResponse(BaseModel):
    days: Literal[7, 30]
    timezone: str
    period_started_at: datetime
    period_ends_at: datetime
    channel: Literal["web", "facebook", "zalo"] | None
    agent_public_id: UUID | None
    summary: AnalyticsSummary
    first_response: AnalyticsResponseTiming
    human_response: AnalyticsResponseTiming
    resolution: AnalyticsResolution
    lead_conversion: AnalyticsLeadConversion
    activity: list[AnalyticsActivityPoint]
    by_channel: list[AnalyticsBreakdown]
    by_agent: list[AnalyticsBreakdown]
    product_interest: list[AnalyticsProductInterest]
    agent_options: list[AnalyticsAgentOption]
