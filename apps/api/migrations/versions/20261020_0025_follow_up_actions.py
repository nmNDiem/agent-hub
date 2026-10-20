"""Add the bounded follow-up Agent action.

Revision ID: 20261020_0025
Revises: 20261020_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_0025"
down_revision: str | None = "20261020_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "follow_up_action_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "agent_revisions",
        sa.Column(
            "follow_up_action_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    op.add_column("leads", sa.Column("revision_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "leads",
        sa.Column("source_channel", sa.String(16), nullable=False, server_default="web"),
    )
    op.add_column(
        "leads",
        sa.Column(
            "capture_source", sa.String(24), nullable=False, server_default="website_form"
        ),
    )
    op.execute(
        """
        UPDATE leads l
        SET revision_id = c.revision_id
        FROM conversations c
        WHERE c.workspace_id = l.workspace_id AND c.id = l.conversation_id
        """
    )
    op.alter_column("leads", "revision_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("leads", "session_id", existing_type=sa.BigInteger(), nullable=True)
    op.alter_column(
        "leads", "consent_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.alter_column(
        "leads", "consent_text_version", existing_type=sa.String(80), nullable=True
    )
    op.drop_constraint("ck_leads_contact_present", "leads", type_="check")
    op.create_unique_constraint("uq_leads_workspace_id", "leads", ["workspace_id", "id"])
    op.create_foreign_key(
        "fk_leads_workspace_revision",
        "leads",
        "agent_revisions",
        ["workspace_id", "agent_id", "revision_id"],
        ["workspace_id", "agent_id", "id"],
    )
    op.create_check_constraint(
        "ck_leads_source_channel",
        "leads",
        "source_channel IN ('web','facebook','zalo')",
    )
    op.create_check_constraint(
        "ck_leads_capture_source",
        "leads",
        "capture_source IN ('website_form','agent_action')",
    )
    op.create_check_constraint(
        "ck_leads_capture_shape",
        "leads",
        "(capture_source = 'website_form' AND source_channel = 'web' "
        "AND session_id IS NOT NULL AND consent_at IS NOT NULL "
        "AND consent_text_version IS NOT NULL "
        "AND (normalized_email IS NOT NULL OR phone IS NOT NULL)) "
        "OR (capture_source = 'agent_action' AND ("
        "(source_channel = 'web' AND session_id IS NOT NULL "
        "AND (normalized_email IS NOT NULL OR phone IS NOT NULL)) "
        "OR (source_channel IN ('facebook','zalo') AND session_id IS NULL)))",
    )

    op.create_table(
        "follow_up_action_executions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column(
            "action_identifier",
            sa.String(64),
            nullable=False,
            server_default="contacts.follow_up.request",
        ),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="executing"),
        sa.Column("safe_outcome", sa.String(40), nullable=True),
        sa.Column("safe_error_code", sa.String(64), nullable=True),
        sa.Column("replay_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "action_identifier = 'contacts.follow_up.request'",
            name="ck_follow_up_executions_action",
        ),
        sa.CheckConstraint(
            "length(request_hash) = 64", name="ck_follow_up_executions_hash"
        ),
        sa.CheckConstraint(
            "state IN ('executing','succeeded','failed_retryable','failed_terminal')",
            name="ck_follow_up_executions_state",
        ),
        sa.CheckConstraint("replay_count >= 0", name="ck_follow_up_executions_replay_count"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_follow_up_executions_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_follow_up_executions_workspace_revision",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_follow_up_executions_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_follow_up_executions_workspace_message",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_follow_up_executions_workspace_contact",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "lead_id"],
            ["leads.workspace_id", "leads.id"],
            name="fk_follow_up_executions_workspace_lead",
        ),
        sa.UniqueConstraint("action_id", name="uq_follow_up_action_executions_action_id"),
        sa.UniqueConstraint(
            "workspace_id", "id", name="uq_follow_up_executions_workspace_id"
        ),
        sa.UniqueConstraint(
            "source_message_id", name="uq_follow_up_executions_source_message"
        ),
        sa.UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_follow_up_executions_idempotency"
        ),
    )
    op.create_index(
        "ix_follow_up_action_executions_workspace_id",
        "follow_up_action_executions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_follow_up_executions_workspace_conversation",
        "follow_up_action_executions",
        ["workspace_id", "conversation_id", "created_at"],
    )
    op.create_index(
        "ix_follow_up_executions_retention",
        "follow_up_action_executions",
        ["retention_until", "id"],
    )


def downgrade() -> None:
    op.drop_table("follow_up_action_executions")
    op.execute("DELETE FROM leads WHERE capture_source = 'agent_action'")
    op.drop_constraint("ck_leads_capture_shape", "leads", type_="check")
    op.drop_constraint("ck_leads_capture_source", "leads", type_="check")
    op.drop_constraint("ck_leads_source_channel", "leads", type_="check")
    op.drop_constraint("fk_leads_workspace_revision", "leads", type_="foreignkey")
    op.drop_constraint("uq_leads_workspace_id", "leads", type_="unique")
    op.create_check_constraint(
        "ck_leads_contact_present",
        "leads",
        "normalized_email IS NOT NULL OR phone IS NOT NULL",
    )
    op.alter_column(
        "leads", "consent_text_version", existing_type=sa.String(80), nullable=False
    )
    op.alter_column(
        "leads", "consent_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
    op.alter_column("leads", "session_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_column("leads", "capture_source")
    op.drop_column("leads", "source_channel")
    op.drop_column("leads", "revision_id")
    op.drop_column("agent_revisions", "follow_up_action_enabled")
    op.drop_column("agents", "follow_up_action_enabled")
