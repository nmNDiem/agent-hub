"""Add conversation indexes and workspace usage ledger.

Revision ID: 20261004_0012
Revises: 20261004_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0012"
down_revision: str | None = "20261004_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_usage_months",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("period_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_turns", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("generated_turns >= 0", name="ck_workspace_usage_turns"),
        sa.UniqueConstraint(
            "workspace_id", "period_started_at", name="uq_workspace_usage_month_period"
        ),
    )
    op.create_index(
        "ix_workspace_usage_months_workspace_id", "workspace_usage_months", ["workspace_id"]
    )
    op.create_index(
        "ix_workspace_usage_period",
        "workspace_usage_months",
        ["period_started_at", "workspace_id"],
    )
    op.create_table(
        "usage_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("surface", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="completed", nullable=False),
        sa.Column("provider", sa.String(40), nullable=True),
        sa.Column("model", sa.String(160), nullable=True),
        sa.Column("model_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tool_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_usage_events_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_usage_events_workspace_conversation",
        ),
        sa.CheckConstraint("surface IN ('widget','playground')", name="ck_usage_surface"),
        sa.CheckConstraint("kind IN ('generation','vision')", name="ck_usage_kind"),
        sa.CheckConstraint("status IN ('completed','failed')", name="ck_usage_status"),
        sa.CheckConstraint("model_calls >= 0", name="ck_usage_model_calls"),
        sa.CheckConstraint("tool_calls >= 0", name="ck_usage_tool_calls"),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0", name="ck_usage_input_tokens"
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0", name="ck_usage_output_tokens"
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0", name="ck_usage_total_tokens"
        ),
    )
    op.create_index("ix_usage_events_workspace_id", "usage_events", ["workspace_id"])
    op.create_index(
        "ix_usage_events_workspace_time",
        "usage_events",
        ["workspace_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_usage_events_workspace_kind_time",
        "usage_events",
        ["workspace_id", "kind", "occurred_at"],
    )
    op.create_index(
        "ix_conversations_workspace_activity_public",
        "conversations",
        ["workspace_id", "last_message_at", "public_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_workspace_activity_public", table_name="conversations")
    op.drop_table("usage_events")
    op.drop_table("workspace_usage_months")
