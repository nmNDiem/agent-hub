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
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_leads_workspace_contact",
        ),
        UniqueConstraint("conversation_id", name="uq_leads_conversation"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_leads_session_idempotency"),
        CheckConstraint(
            "normalized_email IS NOT NULL OR phone IS NOT NULL",
            name="ck_leads_contact_present",
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
    session_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    contact_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    normalized_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consent_text_version: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    followup_status: Mapped[str] = mapped_column(String(16), default="new")
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
