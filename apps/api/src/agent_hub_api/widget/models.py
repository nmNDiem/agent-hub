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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class WebsiteChannelConfig(Base):
    __tablename__ = "website_channel_configs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_website_configs_workspace_connection",
        ),
        UniqueConstraint("workspace_id", "connection_id", name="uq_website_configs_connection"),
        CheckConstraint(
            "launcher_position IN ('left','right')", name="ck_website_configs_launcher_position"
        ),
        CheckConstraint("length(brand_color) = 7", name="ck_website_configs_brand_color"),
    )

    connection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    brand_color: Mapped[str] = mapped_column(String(7), default="#0F8F87")
    launcher_position: Mapped[str] = mapped_column(String(8), default="right")
    handoff_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    handoff_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WidgetDomain(Base):
    __tablename__ = "widget_domains"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "channel_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_widget_domains_workspace_channel",
        ),
        UniqueConstraint("channel_id", "normalized_origin", name="uq_widget_domains_origin"),
        Index("ix_widget_domains_workspace_origin", "workspace_id", "normalized_origin"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    channel_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    normalized_origin: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


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
            ["channel_connections.workspace_id", "channel_connections.id"],
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
        CheckConstraint("cleanup_attempts >= 0", name="ck_visitor_images_cleanup_attempts"),
        Index(
            "ix_visitor_images_workspace_session_expiry",
            "workspace_id",
            "session_id",
            "expires_at",
            "id",
        ),
        Index("ix_visitor_images_cleanup", "status", "expires_at", "id"),
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
    cleanup_attempts: Mapped[int] = mapped_column(Integer(), default=0)
    last_cleanup_error: Mapped[str | None] = mapped_column(String(80), nullable=True)
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
