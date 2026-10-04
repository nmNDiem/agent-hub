from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_agents_workspace_id_id"),
        CheckConstraint("length(trim(name)) > 0", name="ck_agents_name_nonempty"),
        CheckConstraint(
            "status IN ('draft','published','paused')",
            name="ck_agents_status",
        ),
        Index("ix_agents_workspace_status_created", "workspace_id", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    public_id: Mapped[UUID] = mapped_column(unique=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    greeting: Mapped[str | None] = mapped_column(Text(), nullable=True)
    safe_instructions: Mapped[str | None] = mapped_column(Text(), nullable=True)
    default_locale: Mapped[str] = mapped_column(String(16), default="vi")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    all_locations: Mapped[bool] = mapped_column(Boolean(), default=True)
    all_collections: Mapped[bool] = mapped_column(Boolean(), default=True)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AgentLocation(Base):
    __tablename__ = "agent_locations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_agent_locations_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "location_id"],
            ["locations.workspace_id", "locations.id"],
            name="fk_agent_locations_workspace_location",
        ),
        Index("ix_agent_locations_workspace_location", "workspace_id", "location_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    location_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)


class AgentCatalogCollection(Base):
    __tablename__ = "agent_catalog_collections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_agent_collections_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "collection_id"],
            ["catalog_collections.workspace_id", "catalog_collections.id"],
            name="fk_agent_collections_workspace_collection",
        ),
        Index("ix_agent_collections_workspace_collection", "workspace_id", "collection_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    collection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)


class AgentRevision(Base):
    __tablename__ = "agent_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_agent_revisions_workspace_agent",
        ),
        UniqueConstraint(
            "workspace_id", "agent_id", "id", name="uq_agent_revisions_workspace_agent_id"
        ),
        UniqueConstraint("agent_id", "revision_no", name="uq_agent_revisions_agent_number"),
        CheckConstraint("revision_no > 0", name="ck_agent_revisions_number"),
        CheckConstraint("length(config_hash) = 64", name="ck_agent_revisions_config_hash"),
        Index(
            "ix_agent_revisions_workspace_agent_published",
            "workspace_id",
            "agent_id",
            "published_at",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    revision_no: Mapped[int]
    name: Mapped[str] = mapped_column(String(160))
    greeting: Mapped[str | None] = mapped_column(Text(), nullable=True)
    safe_instructions: Mapped[str | None] = mapped_column(Text(), nullable=True)
    default_locale: Mapped[str] = mapped_column(String(16))
    catalog_scope_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT)
    knowledge_base_ids_json: Mapped[list[int]] = mapped_column(JSON_DOCUMENT)
    widget_config_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT)
    config_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentWebChannel(Base):
    __tablename__ = "agent_web_channels"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_web_channels_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id", "active_revision_id"],
            [
                "agent_revisions.workspace_id",
                "agent_revisions.agent_id",
                "agent_revisions.id",
            ],
            name="fk_web_channels_workspace_revision",
        ),
        UniqueConstraint("workspace_id", "agent_id", name="uq_web_channels_workspace_agent"),
        UniqueConstraint("workspace_id", "id", name="uq_web_channels_workspace_id"),
        CheckConstraint(
            "launcher_position IN ('left','right')", name="ck_web_channels_launcher_position"
        ),
        CheckConstraint("length(brand_color) = 7", name="ck_web_channels_brand_color"),
        Index("ix_web_channels_workspace_enabled", "workspace_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    brand_color: Mapped[str] = mapped_column(String(7), default="#0F8F87")
    launcher_position: Mapped[str] = mapped_column(String(8), default="right")
    handoff_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    handoff_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active_revision_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WidgetDomain(Base):
    __tablename__ = "widget_domains"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "channel_id"],
            ["agent_web_channels.workspace_id", "agent_web_channels.id"],
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
