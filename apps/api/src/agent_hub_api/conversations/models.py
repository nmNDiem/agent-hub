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
        ForeignKeyConstraint(
            ["workspace_id", "channel_connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_conversations_workspace_connection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "assigned_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_conversations_workspace_assignee",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_conversations_workspace_id"),
        UniqueConstraint("session_id", name="uq_conversations_session"),
        CheckConstraint(
            "lifecycle_state IN ('active','deleted')", name="ck_conversations_lifecycle"
        ),
        CheckConstraint(
            "workflow_status IN ('open','pending','resolved')",
            name="ck_conversations_workflow_status",
        ),
        CheckConstraint(
            "handling_mode IN ('ai','human','paused')", name="ck_conversations_handling_mode"
        ),
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
        Index(
            "ix_conversations_workspace_connection",
            "workspace_id",
            "channel_connection_id",
            "id",
        ),
        Index(
            "ix_conversations_workspace_inbox",
            "workspace_id",
            "workflow_status",
            "assigned_member_id",
            "last_message_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    public_id: Mapped[UUID] = mapped_column(unique=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    revision_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    channel_connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    session_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(16), default="active")
    workflow_status: Mapped[str] = mapped_column(String(16), default="open")
    handling_mode: Mapped[str] = mapped_column(String(16), default="ai")
    assigned_member_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    state_version: Mapped[int] = mapped_column(Integer(), default=1)
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
        UniqueConstraint("workspace_id", "id", name="uq_messages_workspace_id"),
        UniqueConstraint("conversation_id", "sequence_no", name="uq_messages_sequence"),
        UniqueConstraint("conversation_id", "request_key", name="uq_messages_request_key"),
        CheckConstraint(
            "actor IN ('visitor','assistant','human','tool','system')", name="ck_messages_actor"
        ),
        CheckConstraint("direction IN ('inbound','outbound')", name="ck_messages_direction"),
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
    direction: Mapped[str] = mapped_column(String(16))
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


class ConversationReadState(Base):
    __tablename__ = "conversation_read_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_reads_workspace_conversation",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_conversation_reads_workspace_member",
        ),
        UniqueConstraint("conversation_id", "member_id", name="uq_conversation_reads_member"),
        Index("ix_conversation_reads_workspace_member", "workspace_id", "member_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    member_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    last_read_sequence: Mapped[int] = mapped_column(Integer(), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationNote(Base):
    __tablename__ = "conversation_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_notes_workspace_conversation",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "author_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_conversation_notes_workspace_author",
        ),
        Index(
            "ix_conversation_notes_workspace_conversation", "workspace_id", "conversation_id", "id"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    author_member_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    body: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationTag(Base):
    __tablename__ = "conversation_tags"
    __table_args__ = (
        UniqueConstraint("workspace_id", "normalized_name", name="uq_conversation_tags_name"),
        UniqueConstraint("workspace_id", "id", name="uq_conversation_tags_workspace_id"),
        Index("ix_conversation_tags_workspace_name", "workspace_id", "normalized_name"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(48))
    normalized_name: Mapped[str] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationTagLink(Base):
    __tablename__ = "conversation_tag_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_tag_links_workspace_conversation",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "tag_id"],
            ["conversation_tags.workspace_id", "conversation_tags.id"],
            name="fk_conversation_tag_links_workspace_tag",
        ),
        UniqueConstraint("conversation_id", "tag_id", name="uq_conversation_tag_links_pair"),
        Index(
            "ix_conversation_tag_links_workspace_tag", "workspace_id", "tag_id", "conversation_id"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    tag_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationAuditEvent(Base):
    __tablename__ = "conversation_audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_audit_workspace_conversation",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "actor_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_conversation_audit_workspace_actor",
        ),
        Index(
            "ix_conversation_audit_workspace_conversation", "workspace_id", "conversation_id", "id"
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    actor_member_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    event_type: Mapped[str] = mapped_column(String(32))
    details_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
