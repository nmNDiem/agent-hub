"""Add agent configuration and catalog scope assignments.

Revision ID: 20260927_0006
Revises: 20260925_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_0006"
down_revision: str | None = "20260925_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=True),
        sa.Column("safe_instructions", sa.Text(), nullable=True),
        sa.Column("default_locale", sa.String(16), server_default="vi", nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("all_locations", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("all_collections", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_agents_name_nonempty"),
        sa.CheckConstraint(
            "status IN ('draft','published','paused')",
            name="ck_agents_status",
        ),
        sa.UniqueConstraint("public_id", name="uq_agents_public_id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_agents_workspace_id_id"),
    )
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])
    op.create_index(
        "ix_agents_workspace_status_created",
        "agents",
        ["workspace_id", "status", "created_at"],
    )

    op.create_table(
        "agent_locations",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("agent_id", sa.BigInteger(), primary_key=True),
        sa.Column("location_id", sa.BigInteger(), primary_key=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_agent_locations_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "location_id"],
            ["locations.workspace_id", "locations.id"],
            name="fk_agent_locations_workspace_location",
        ),
    )
    op.create_index(
        "ix_agent_locations_workspace_location",
        "agent_locations",
        ["workspace_id", "location_id"],
    )

    op.create_table(
        "agent_catalog_collections",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("agent_id", sa.BigInteger(), primary_key=True),
        sa.Column("collection_id", sa.BigInteger(), primary_key=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_agent_collections_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "collection_id"],
            ["catalog_collections.workspace_id", "catalog_collections.id"],
            name="fk_agent_collections_workspace_collection",
        ),
    )
    op.create_index(
        "ix_agent_collections_workspace_collection",
        "agent_catalog_collections",
        ["workspace_id", "collection_id"],
    )


def downgrade() -> None:
    op.drop_table("agent_catalog_collections")
    op.drop_table("agent_locations")
    op.drop_table("agents")
