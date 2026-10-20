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


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_leads_workspace_conversation",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "session_id"],
            ["widget_sessions.workspace_id", "widget_sessions.id"],
            name="fk_leads_workspace_session",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_leads_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_leads_workspace_revision",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_leads_workspace_contact",
        ),
        UniqueConstraint("conversation_id", name="uq_leads_conversation"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_leads_session_idempotency"),
        UniqueConstraint("workspace_id", "id", name="uq_leads_workspace_id"),
        CheckConstraint(
            "source_channel IN ('web','facebook','zalo')",
            name="ck_leads_source_channel",
        ),
        CheckConstraint(
            "capture_source IN ('website_form','agent_action')",
            name="ck_leads_capture_source",
        ),
        CheckConstraint(
            "(capture_source = 'website_form' AND source_channel = 'web' "
            "AND session_id IS NOT NULL AND consent_at IS NOT NULL "
            "AND consent_text_version IS NOT NULL "
            "AND (normalized_email IS NOT NULL OR phone IS NOT NULL)) "
            "OR (capture_source = 'agent_action' AND ("
            "(source_channel = 'web' AND session_id IS NOT NULL "
            "AND (normalized_email IS NOT NULL OR phone IS NOT NULL)) "
            "OR (source_channel IN ('facebook','zalo') AND session_id IS NULL)))",
            name="ck_leads_capture_shape",
        ),
        CheckConstraint(
            "followup_status IN ('new','contacted','closed')",
            name="ck_leads_followup_status",
        ),
        CheckConstraint("length(request_hash) = 64", name="ck_leads_request_hash"),
        Index(
            "ix_leads_workspace_status_created",
            "workspace_id",
            "followup_status",
            "created_at",
            "id",
        ),
        Index("ix_leads_retention", "retention_until", "id"),
        Index("ix_leads_workspace_contact", "workspace_id", "contact_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    session_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    revision_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    contact_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    normalized_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_channel: Mapped[str] = mapped_column(String(16), default="web")
    capture_source: Mapped[str] = mapped_column(String(24), default="website_form")
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_text_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    followup_status: Mapped[str] = mapped_column(String(16), default="new")
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
