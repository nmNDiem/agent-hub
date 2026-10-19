from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from agent_hub_api.agents.schemas import AgentIcon

DependencyState = Literal["ready", "partial", "stale", "unavailable"]
AttentionReason = Literal[
    "knowledge_stale",
    "knowledge_failed",
    "website_not_ready",
    "channel_disconnected",
    "channel_degraded",
    "handover_pending",
]


class OverviewDependency(BaseModel):
    state: DependencyState
    reason: str | None = None


class OverviewDependencies(BaseModel):
    agents: OverviewDependency
    knowledge: OverviewDependency
    channels: OverviewDependency
    conversations: OverviewDependency
    catalog: OverviewDependency


class OverviewCatalogCapability(BaseModel):
    available: bool
    can_setup: bool


class OverviewCapabilities(BaseModel):
    catalog: OverviewCatalogCapability


class OverviewRelationshipCollection(BaseModel):
    total: int = Field(ge=0)
    truncated: bool


class OverviewKnowledgeItem(BaseModel):
    id: int
    name: str
    kind: Literal["shop", "faq", "policy", "general"]
    state: Literal["ready", "stale", "failed"]


class OverviewKnowledgeCollection(OverviewRelationshipCollection):
    items: list[OverviewKnowledgeItem]


class OverviewChannelItem(BaseModel):
    id: int
    provider: Literal["web", "facebook", "zalo"]
    display_name: str
    lifecycle_state: Literal["active", "revoked"]
    health_state: Literal[
        "unknown",
        "healthy",
        "permission_expired",
        "reauth_required",
        "webhook_subscription_failure",
        "delivery_unknown",
    ]
    enabled: bool
    active_revision_id: int | None


class OverviewChannelCollection(OverviewRelationshipCollection):
    items: list[OverviewChannelItem]


class OverviewChannelGroups(BaseModel):
    web: OverviewChannelCollection
    facebook: OverviewChannelCollection
    zalo: OverviewChannelCollection


class OverviewCatalogReference(BaseModel):
    id: int
    name: str


class OverviewCatalogReferenceCollection(OverviewRelationshipCollection):
    all_accessible: bool
    items: list[OverviewCatalogReference]


class OverviewCatalogScope(BaseModel):
    available: bool
    locations: OverviewCatalogReferenceCollection
    collections: OverviewCatalogReferenceCollection


class OverviewPublishedRevision(BaseModel):
    id: int
    revision_no: int
    published_at: datetime


class OverviewWebsiteReadiness(BaseModel):
    configured: bool
    has_allowed_origin: bool
    has_knowledge: bool
    has_catalog_scope: bool
    can_publish: bool


class OverviewConversationActivity(BaseModel):
    total: int = Field(ge=0)
    open: int = Field(ge=0)
    pending: int = Field(ge=0)
    human_handling: int = Field(ge=0)


class OverviewAgent(BaseModel):
    public_id: UUID
    name: str
    icon: AgentIcon
    color: str
    lifecycle_state: Literal["draft", "published", "paused"]
    updated_at: datetime
    active_revision: OverviewPublishedRevision | None
    knowledge: OverviewKnowledgeCollection
    channels: OverviewChannelGroups
    catalog_scope: OverviewCatalogScope
    website_readiness: OverviewWebsiteReadiness
    conversations: OverviewConversationActivity
    attention_reasons: list[AttentionReason]


class WorkspaceOverviewResponse(BaseModel):
    workspace_id: UUID
    workspace_slug: str
    workspace_name: str
    role: Literal["owner", "admin", "member"]
    generated_at: datetime
    days: Literal[7, 30]
    window_started_at: datetime
    capabilities: OverviewCapabilities
    dependencies: OverviewDependencies
    agent_total: int = Field(ge=0)
    agents_truncated: bool
    agents: list[OverviewAgent]
