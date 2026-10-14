"""Add Zalo OAuth attempts and usage surface.

Revision ID: 20261014_0017
Revises: 20261008_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0017"
down_revision: str | None = "20261008_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_usage_surface", "usage_events", type_="check")
    op.create_check_constraint(
        "ck_usage_surface",
        "usage_events",
        "surface IN ('widget','playground','facebook','zalo')",
    )
    op.create_table(
        "channel_oauth_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("verifier_credential_ref", sa.String(500), nullable=False),
        sa.Column(
            "reauthorize_connection_id",
            sa.BigInteger(),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("succeeded", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_channel_oauth_attempts_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_channel_oauth_attempts_workspace_revision",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "reauthorize_connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_channel_oauth_attempts_workspace_connection",
        ),
        sa.UniqueConstraint("state_hash", name="uq_channel_oauth_attempts_state_hash"),
        sa.CheckConstraint("provider IN ('zalo')", name="ck_channel_oauth_attempts_provider"),
    )
    op.create_index(
        "ix_channel_oauth_attempts_workspace_id", "channel_oauth_attempts", ["workspace_id"]
    )
    op.create_index("ix_channel_oauth_attempts_user_id", "channel_oauth_attempts", ["user_id"])
    op.create_index(
        "ix_channel_oauth_attempts_expiry",
        "channel_oauth_attempts",
        ["expires_at", "consumed_at", "id"],
    )
    op.create_index(
        "ix_channel_oauth_attempts_workspace",
        "channel_oauth_attempts",
        ["workspace_id", "provider", "id"],
    )


def downgrade() -> None:
    op.execute("DELETE FROM usage_events WHERE surface = 'zalo'")
    op.drop_table("channel_oauth_attempts")
    op.drop_constraint("ck_usage_surface", "usage_events", type_="check")
    op.create_check_constraint(
        "ck_usage_surface",
        "usage_events",
        "surface IN ('widget','playground','facebook')",
    )
