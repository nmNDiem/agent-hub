from datetime import datetime
from uuid import UUID

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now


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
