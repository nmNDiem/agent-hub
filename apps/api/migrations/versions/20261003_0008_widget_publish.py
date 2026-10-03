"""Add immutable agent revisions and website channel configuration.

Revision ID: 20261003_0008
Revises: 20260929_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0008"
down_revision: str | None = "20260929_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_revisions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=True),
        sa.Column("safe_instructions", sa.Text(), nullable=True),
        sa.Column("default_locale", sa.String(16), nullable=False),
        sa.Column("catalog_scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "knowledge_base_ids_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("widget_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_agent_revisions_workspace_agent",
        ),
        sa.CheckConstraint("revision_no > 0", name="ck_agent_revisions_number"),
        sa.CheckConstraint("length(config_hash) = 64", name="ck_agent_revisions_config_hash"),
        sa.UniqueConstraint(
            "workspace_id", "agent_id", "id", name="uq_agent_revisions_workspace_agent_id"
        ),
        sa.UniqueConstraint("agent_id", "revision_no", name="uq_agent_revisions_agent_number"),
    )
    op.create_index("ix_agent_revisions_workspace_id", "agent_revisions", ["workspace_id"])
    op.create_index(
        "ix_agent_revisions_workspace_agent_published",
        "agent_revisions",
        ["workspace_id", "agent_id", "published_at"],
    )

    op.create_table(
        "agent_web_channels",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("brand_color", sa.String(7), server_default="#0F8F87", nullable=False),
        sa.Column("launcher_position", sa.String(8), server_default="right", nullable=False),
        sa.Column("active_revision_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_web_channels_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "active_revision_id"],
            [
                "agent_revisions.workspace_id",
                "agent_revisions.agent_id",
                "agent_revisions.id",
            ],
            name="fk_web_channels_workspace_revision",
        ),
        sa.CheckConstraint(
            "launcher_position IN ('left','right')", name="ck_web_channels_launcher_position"
        ),
        sa.CheckConstraint("length(brand_color) = 7", name="ck_web_channels_brand_color"),
        sa.UniqueConstraint("workspace_id", "agent_id", name="uq_web_channels_workspace_agent"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_web_channels_workspace_id"),
    )
    op.create_index("ix_agent_web_channels_workspace_id", "agent_web_channels", ["workspace_id"])
    op.create_index(
        "ix_web_channels_workspace_enabled",
        "agent_web_channels",
        ["workspace_id", "enabled"],
    )

    op.create_table(
        "widget_domains",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("normalized_origin", sa.String(300), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "channel_id"],
            ["agent_web_channels.workspace_id", "agent_web_channels.id"],
            name="fk_widget_domains_workspace_channel",
        ),
        sa.UniqueConstraint("channel_id", "normalized_origin", name="uq_widget_domains_origin"),
    )
    op.create_index("ix_widget_domains_workspace_id", "widget_domains", ["workspace_id"])
    op.create_index(
        "ix_widget_domains_workspace_origin",
        "widget_domains",
        ["workspace_id", "normalized_origin"],
    )

    op.execute(
        """
        CREATE FUNCTION prevent_agent_revision_update() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'agent revisions are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_agent_revisions_immutable
        BEFORE UPDATE ON agent_revisions
        FOR EACH ROW EXECUTE FUNCTION prevent_agent_revision_update()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_agent_revisions_immutable ON agent_revisions")
    op.execute("DROP FUNCTION IF EXISTS prevent_agent_revision_update()")
    op.drop_table("widget_domains")
    op.drop_table("agent_web_channels")
    op.drop_table("agent_revisions")
