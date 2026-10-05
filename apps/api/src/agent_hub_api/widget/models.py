from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class WidgetSession(Base):
    __tablename__ = "widget_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_widget_sessions_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "channel_id"],
            ["agent_web_channels.workspace_id", "agent_web_channels.id"],
            name="fk_widget_sessions_workspace_channel",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            [
                "agent_revisions.workspace_id",
                "agent_revisions.agent_id",
                "agent_revisions.id",
            ],
            name="fk_widget_sessions_workspace_revision",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_widget_sessions_workspace_id"),
        Index("ix_widget_sessions_workspace_expiry", "workspace_id", "expires_at", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    channel_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    revision_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    normalized_origin: Mapped[str] = mapped_column(String(300))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_conversations_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "session_id"],
            ["widget_sessions.workspace_id", "widget_sessions.id"],
            name="fk_conversations_workspace_session",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            [
                "agent_revisions.workspace_id",
                "agent_revisions.agent_id",
                "agent_revisions.id",
            ],
            name="fk_conversations_workspace_revision",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_conversations_workspace_id"),
        UniqueConstraint("session_id", name="uq_conversations_session"),
        CheckConstraint("status IN ('open','deleted')", name="ck_conversations_status"),
        Index(
            "ix_conversations_workspace_last_message",
            "workspace_id",
            "last_message_at",
            "id",
        ),
        Index(
            "ix_conversations_workspace_activity_public",
            "workspace_id",
            "last_message_at",
            "public_id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    public_id: Mapped[UUID] = mapped_column(unique=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    revision_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    session_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    status: Mapped[str] = mapped_column(String(16), default="open")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_messages_workspace_conversation",
        ),
        UniqueConstraint("conversation_id", "sequence_no", name="uq_messages_sequence"),
        UniqueConstraint("conversation_id", "request_key", name="uq_messages_request_key"),
        CheckConstraint("actor IN ('visitor','assistant')", name="ck_messages_actor"),
        CheckConstraint(
            "status IN ('pending','completed','failed','cancelled')",
            name="ck_messages_status",
        ),
        CheckConstraint("sequence_no > 0", name="ck_messages_sequence_positive"),
        Index(
            "uq_messages_active_assistant",
            "conversation_id",
            unique=True,
            postgresql_where=text("actor = 'assistant' AND status = 'pending'"),
            sqlite_where=text("actor = 'assistant' AND status = 'pending'"),
        ),
        Index("ix_messages_workspace_conversation", "workspace_id", "conversation_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    sequence_no: Mapped[int] = mapped_column(Integer())
    actor: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text(), default="")
    status: Mapped[str] = mapped_column(String(16))
    request_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_id: Mapped[UUID | None] = mapped_column(unique=True, nullable=True)
    response_json: Mapped[dict[str, object] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    output_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    total_tokens: Mapped[int] = mapped_column(Integer(), default=0)
    generation_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WidgetRateWindow(Base):
    __tablename__ = "widget_rate_windows"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "scope",
            "key_hash",
            "window_started_at",
            name="uq_widget_rate_windows_bucket",
        ),
        CheckConstraint("count >= 0", name="ck_widget_rate_windows_count"),
        Index("ix_widget_rate_windows_expiry", "window_started_at", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    scope: Mapped[str] = mapped_column(String(40))
    key_hash: Mapped[str] = mapped_column(String(64))
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer(), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class VisitorImageUpload(Base):
    __tablename__ = "visitor_image_uploads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "session_id"],
            ["widget_sessions.workspace_id", "widget_sessions.id"],
            name="fk_visitor_images_workspace_session",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "attached_conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_visitor_images_workspace_conversation",
        ),
        CheckConstraint(
            "status IN ('uploading','available','attached','cleanup_pending','deleted')",
            name="ck_visitor_images_status",
        ),
        CheckConstraint("byte_size > 0", name="ck_visitor_images_byte_size"),
        CheckConstraint("width > 0 AND height > 0", name="ck_visitor_images_dimensions"),
        Index(
            "ix_visitor_images_workspace_session_expiry",
            "workspace_id",
            "session_id",
            "expires_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    public_id: Mapped[UUID] = mapped_column(unique=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    session_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    attached_conversation_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    attached_request_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(900), unique=True, nullable=True)
    content_type: Mapped[str] = mapped_column(String(40))
    byte_size: Mapped[int] = mapped_column(Integer())
    width: Mapped[int] = mapped_column(Integer())
    height: Mapped[int] = mapped_column(Integer())
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="uploading")
    analysis_json: Mapped[dict[str, object] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WidgetCatalogImageGrant(Base):
    __tablename__ = "widget_catalog_image_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "session_id"],
            ["widget_sessions.workspace_id", "widget_sessions.id"],
            name="fk_widget_image_grants_workspace_session",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "product_image_id"],
            ["product_images.workspace_id", "product_images.id"],
            name="fk_widget_image_grants_workspace_image",
        ),
        UniqueConstraint(
            "session_id",
            "product_image_id",
            name="uq_widget_image_grants_session_image",
        ),
        Index(
            "ix_widget_image_grants_workspace_expiry",
            "workspace_id",
            "expires_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    public_id: Mapped[UUID] = mapped_column(unique=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    session_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    product_image_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
