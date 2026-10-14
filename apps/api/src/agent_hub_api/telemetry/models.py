from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now


class WorkspaceUsageMonth(Base):
    __tablename__ = "workspace_usage_months"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "period_started_at", name="uq_workspace_usage_month_period"
        ),
        CheckConstraint("generated_turns >= 0", name="ck_workspace_usage_turns"),
        Index("ix_workspace_usage_period", "period_started_at", "workspace_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    period_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    generated_turns: Mapped[int] = mapped_column(Integer(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_usage_events_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_usage_events_workspace_conversation",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "surface IN ('widget','playground','facebook','zalo')", name="ck_usage_surface"
        ),
        CheckConstraint("kind IN ('generation','vision')", name="ck_usage_kind"),
        CheckConstraint("status IN ('completed','failed')", name="ck_usage_status"),
        CheckConstraint("model_calls >= 0", name="ck_usage_model_calls"),
        CheckConstraint("tool_calls >= 0", name="ck_usage_tool_calls"),
        CheckConstraint("input_tokens IS NULL OR input_tokens >= 0", name="ck_usage_input_tokens"),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0", name="ck_usage_output_tokens"
        ),
        CheckConstraint("total_tokens IS NULL OR total_tokens >= 0", name="ck_usage_total_tokens"),
        Index("ix_usage_events_workspace_time", "workspace_id", "occurred_at", "id"),
        Index("ix_usage_events_workspace_kind_time", "workspace_id", "kind", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    conversation_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    surface: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="completed")
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    model_calls: Mapped[int] = mapped_column(Integer(), default=0)
    tool_calls: Mapped[int] = mapped_column(Integer(), default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
