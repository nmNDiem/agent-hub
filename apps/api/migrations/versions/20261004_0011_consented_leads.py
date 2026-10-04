"""Add consented leads and published contact handoff.

Revision ID: 20261004_0011
Revises: 20261004_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0011"
down_revision: str | None = "20261004_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_web_channels", sa.Column("handoff_url", sa.String(500), nullable=True))
    op.add_column(
        "agent_web_channels", sa.Column("handoff_label", sa.String(80), nullable=True)
    )
    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("normalized_email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_text_version", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("followup_status", sa.String(16), server_default="new", nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_leads_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "session_id"],
            ["widget_sessions.workspace_id", "widget_sessions.id"],
            name="fk_leads_workspace_session",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_leads_workspace_agent",
        ),
        sa.CheckConstraint(
            "normalized_email IS NOT NULL OR phone IS NOT NULL",
            name="ck_leads_contact_present",
        ),
        sa.CheckConstraint(
            "followup_status IN ('new','contacted','closed')",
            name="ck_leads_followup_status",
        ),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_leads_request_hash"),
        sa.UniqueConstraint("conversation_id", name="uq_leads_conversation"),
        sa.UniqueConstraint(
            "session_id", "idempotency_key", name="uq_leads_session_idempotency"
        ),
    )
    op.create_index("ix_leads_workspace_id", "leads", ["workspace_id"])
    op.create_index(
        "ix_leads_workspace_status_created",
        "leads",
        ["workspace_id", "followup_status", "created_at", "id"],
    )
    op.create_index("ix_leads_retention", "leads", ["retention_until", "id"])


def downgrade() -> None:
    op.drop_table("leads")
    op.drop_column("agent_web_channels", "handoff_label")
    op.drop_column("agent_web_channels", "handoff_url")
