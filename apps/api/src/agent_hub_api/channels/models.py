from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
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
        CheckConstraint("lifecycle_state IN ('active','revoked')", name="ck_connections_lifecycle"),
        CheckConstraint(
            "health_state IN "
            "('unknown','healthy','permission_expired','reauth_required',"
            "'webhook_subscription_failure','delivery_unknown')",
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


class ChannelOAuthAttempt(Base):
    __tablename__ = "channel_oauth_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_channel_oauth_attempts_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_channel_oauth_attempts_workspace_revision",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "reauthorize_connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_channel_oauth_attempts_workspace_connection",
        ),
        UniqueConstraint("state_hash", name="uq_channel_oauth_attempts_state_hash"),
        CheckConstraint("provider IN ('zalo')", name="ck_channel_oauth_attempts_provider"),
        Index("ix_channel_oauth_attempts_expiry", "expires_at", "consumed_at", "id"),
        Index("ix_channel_oauth_attempts_workspace", "workspace_id", "provider", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    revision_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    provider: Mapped[str] = mapped_column(String(16))
    state_hash: Mapped[str] = mapped_column(String(64))
    verifier_credential_ref: Mapped[str] = mapped_column(String(500))
    reauthorize_connection_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    succeeded: Mapped[bool] = mapped_column(Boolean(), default=False)
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


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
        CheckConstraint(
            "automation_state IN ('opted_in','opted_out')",
            name="ck_thread_mappings_automation",
        ),
        Index("ix_thread_mappings_workspace_connection", "workspace_id", "connection_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    external_thread_id: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    automation_state: Mapped[str] = mapped_column(String(16), default="opted_in")


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
            "state IN "
            "('queued','sending','accepted','delivered','failed_retryable','failed_terminal')",
            name="ck_deliveries_state",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_deliveries_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_deliveries_max_attempts"),
        Index("ix_deliveries_claim", "state", "next_attempt_at", "lease_expires_at", "id"),
        Index(
            "ix_deliveries_connection_provider_message",
            "connection_id",
            "provider_message_id",
        ),
        Index("ix_deliveries_workspace_connection", "workspace_id", "connection_id", "id"),
        Index("ix_deliveries_workspace_created", "workspace_id", "created_at", "id"),
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
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ChannelDeliveryReceipt(Base):
    __tablename__ = "channel_delivery_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_delivery_receipts_workspace_connection",
        ),
        UniqueConstraint(
            "connection_id",
            "provider_message_id",
            name="uq_delivery_receipt_provider_message",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_delivery_receipts_workspace_id"),
        Index(
            "ix_delivery_receipts_workspace_connection",
            "workspace_id",
            "connection_id",
            "received_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    provider_message_id: Mapped[str] = mapped_column(String(500))
    external_thread_id: Mapped[str] = mapped_column(String(500))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ChannelResponseJob(Base):
    __tablename__ = "channel_response_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_response_jobs_workspace_connection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_response_jobs_workspace_conversation",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "inbound_message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_response_jobs_workspace_inbound_message",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "outbound_message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_response_jobs_workspace_outbound_message",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_response_jobs_workspace_id"),
        UniqueConstraint("inbound_message_id", name="uq_response_jobs_inbound_message"),
        CheckConstraint(
            "state IN ('queued','running','completed','failed_retryable',"
            "'failed_terminal','suppressed')",
            name="ck_response_jobs_state",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_response_jobs_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_response_jobs_max_attempts"),
        Index("ix_response_jobs_claim", "state", "next_attempt_at", "lease_expires_at", "id"),
        Index("ix_response_jobs_workspace_connection", "workspace_id", "connection_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    inbound_message_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    outbound_message_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    state: Mapped[str] = mapped_column(String(24), default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer(), default=0)
    max_attempts: Mapped[int] = mapped_column(Integer(), default=3)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ChannelInboundMedia(Base):
    __tablename__ = "channel_inbound_media"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_inbound_media_workspace_connection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_inbound_media_workspace_message",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_inbound_media_workspace_id"),
        UniqueConstraint("connection_id", "provider_media_id", name="uq_inbound_media_provider_id"),
        CheckConstraint("kind IN ('image','audio','video','file')", name="ck_inbound_media_kind"),
        CheckConstraint(
            "state IN ('pending','available','unsupported','cleanup_pending','deleted','failed')",
            name="ck_inbound_media_state",
        ),
        CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="ck_inbound_media_bytes"),
        Index("ix_inbound_media_cleanup", "state", "expires_at", "id"),
        Index("ix_inbound_media_workspace_message", "workspace_id", "message_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    message_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    provider_media_id: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(24), default="pending")
    # Cleared immediately after the worker's bounded fetch attempt; never returned or logged.
    source_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    height: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
