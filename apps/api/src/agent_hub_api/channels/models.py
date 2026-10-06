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


class ChannelConnection(Base):
    __tablename__ = "channel_connections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_channel_connections_workspace_id"),
        UniqueConstraint(
            "provider", "external_account_id", name="uq_channel_connections_provider_account"
        ),
        CheckConstraint("provider IN ('web','facebook','zalo')", name="ck_connections_provider"),
        CheckConstraint(
            "lifecycle_state IN ('active','revoked')", name="ck_connections_lifecycle"
        ),
        CheckConstraint(
            "health_state IN ('unknown','healthy','degraded','error')",
            name="ck_connections_health",
        ),
        Index("ix_connections_workspace_provider", "workspace_id", "provider", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    display_name: Mapped[str] = mapped_column(String(160))
    external_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credential_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(16), default="active")
    health_state: Mapped[str] = mapped_column(String(16), default="unknown")
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
class ChannelAgentBinding(Base):
    __tablename__ = "channel_agent_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_channel_bindings_workspace_connection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_channel_bindings_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id", "active_revision_id"],
            [
                "agent_revisions.workspace_id",
                "agent_revisions.agent_id",
                "agent_revisions.id",
            ],
            name="fk_channel_bindings_workspace_revision",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_channel_bindings_workspace_id"),
        UniqueConstraint("connection_id", name="uq_channel_bindings_connection"),
        Index("ix_channel_bindings_workspace_agent", "workspace_id", "agent_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    active_revision_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ChannelWebhookEvent(Base):
    __tablename__ = "channel_webhook_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_webhook_events_workspace_connection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_webhook_events_workspace_message",
        ),
        UniqueConstraint("connection_id", "external_event_id", name="uq_webhook_event_external"),
        CheckConstraint(
            "state IN ('received','processed','failed')", name="ck_webhook_events_state"
        ),
        Index("ix_webhook_events_processing", "state", "received_at", "id"),
        Index("ix_webhook_events_workspace_connection", "workspace_id", "connection_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    external_event_id: Mapped[str] = mapped_column(String(255))
    payload_fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="received")
    message_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    provider_occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelThreadMapping(Base):
    __tablename__ = "channel_thread_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_thread_mappings_workspace_connection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_thread_mappings_workspace_conversation",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_thread_mappings_workspace_id"),
        UniqueConstraint("connection_id", "external_thread_id", name="uq_thread_external"),
        UniqueConstraint("conversation_id", name="uq_thread_conversation"),
        Index("ix_thread_mappings_workspace_connection", "workspace_id", "connection_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    external_thread_id: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChannelMessageMapping(Base):
    __tablename__ = "channel_message_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_message_mappings_workspace_connection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_message_mappings_workspace_message",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "thread_mapping_id"],
            ["channel_thread_mappings.workspace_id", "channel_thread_mappings.id"],
            name="fk_message_mappings_workspace_thread",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_message_mappings_workspace_id"),
        UniqueConstraint("connection_id", "message_id", name="uq_message_mapping_message"),
        UniqueConstraint(
            "connection_id", "external_message_id", name="uq_message_mapping_external"
        ),
        CheckConstraint("direction IN ('inbound','outbound')", name="ck_message_mapping_direction"),
        Index("ix_message_mappings_workspace_connection", "workspace_id", "connection_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    thread_mapping_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    message_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    external_message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    direction: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OutboundDelivery(Base):
    __tablename__ = "outbound_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_deliveries_workspace_connection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_deliveries_workspace_message",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_deliveries_workspace_id"),
        UniqueConstraint("connection_id", "idempotency_key", name="uq_delivery_idempotency"),
        UniqueConstraint("connection_id", "message_id", name="uq_delivery_message"),
        CheckConstraint(
            "state IN ('queued','sending','delivered','failed_retryable','failed_terminal')",
            name="ck_deliveries_state",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_deliveries_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_deliveries_max_attempts"),
        Index("ix_deliveries_claim", "state", "next_attempt_at", "lease_expires_at", "id"),
        Index("ix_deliveries_workspace_connection", "workspace_id", "connection_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    message_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(24), default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0)
    max_attempts: Mapped[int] = mapped_column(Integer(), default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
