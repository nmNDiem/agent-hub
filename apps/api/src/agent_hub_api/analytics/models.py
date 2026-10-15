from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_analytics_events_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_analytics_events_workspace_conversation",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_analytics_events_workspace_message",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_analytics_events_workspace_product",
        ),
        UniqueConstraint(
            "workspace_id",
            "event_type",
            "message_id",
            "product_id",
            name="uq_analytics_events_message_product",
        ),
        CheckConstraint("channel IN ('web','facebook','zalo')", name="ck_analytics_events_channel"),
        CheckConstraint("event_type IN ('product_impression')", name="ck_analytics_events_type"),
        Index("ix_analytics_events_workspace_time", "workspace_id", "occurred_at", "id"),
        Index(
            "ix_analytics_events_workspace_channel_time",
            "workspace_id",
            "channel",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_analytics_events_workspace_agent_time",
            "workspace_id",
            "agent_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_analytics_events_workspace_product_time",
            "workspace_id",
            "product_id",
            "occurred_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    message_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    product_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    channel: Mapped[str] = mapped_column(String(16))
    event_type: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
