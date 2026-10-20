"""Add structured contact intake.

Revision ID: 20261020_0026
Revises: 20261020_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_0026"
down_revision: str | None = "20261020_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column(
        "agents",
        sa.Column("intake_action_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("agents", sa.Column("intake_definition_json", jsonb, nullable=True))
    op.add_column(
        "agent_revisions",
        sa.Column("intake_action_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("agent_revisions", sa.Column("intake_definition_json", jsonb, nullable=True))

    op.add_column("leads", sa.Column("qualification_status", sa.String(24), nullable=True))
    op.add_column(
        "leads",
        sa.Column("qualification_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("leads", sa.Column("qualification_reason", sa.String(500), nullable=True))
    op.add_column(
        "leads",
        sa.Column(
            "qualification_updated_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "leads",
        sa.Column("qualification_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_leads_qualification_status",
        "leads",
        "qualification_status IS NULL OR qualification_status IN "
        "('pending_review','qualified','not_qualified')",
    )
    op.create_check_constraint(
        "ck_leads_qualification_version", "leads", "qualification_version >= 0"
    )
    op.create_index(
        "ix_leads_workspace_qualification",
        "leads",
        ["workspace_id", "qualification_status", "created_at", "id"],
    )

    op.create_table(
        "contact_intake_submissions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("purpose", sa.String(240), nullable=False),
        sa.Column("disclosure_version", sa.String(64), nullable=False),
        sa.Column("definition_hash", sa.String(64), nullable=False),
        sa.Column("definition_json", jsonb, nullable=False),
        sa.Column("answers_json", jsonb, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_intake_submissions_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_intake_submissions_workspace_revision",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_intake_submissions_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_intake_submissions_workspace_message",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_intake_submissions_workspace_contact",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "lead_id"],
            ["leads.workspace_id", "leads.id"],
            name="fk_intake_submissions_workspace_lead",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_intake_submissions_workspace_id"),
        sa.UniqueConstraint("conversation_id", name="uq_intake_submissions_conversation"),
        sa.CheckConstraint("state = 'completed'", name="ck_intake_submissions_state"),
        sa.CheckConstraint(
            "length(definition_hash) = 64", name="ck_intake_submissions_definition_hash"
        ),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_intake_submissions_request_hash"),
    )
    op.create_index(
        "ix_intake_submissions_workspace_id", "contact_intake_submissions", ["workspace_id"]
    )
    op.create_index(
        "ix_intake_submissions_workspace_lead",
        "contact_intake_submissions",
        ["workspace_id", "lead_id", "submitted_at"],
    )
    op.create_index(
        "ix_intake_submissions_retention",
        "contact_intake_submissions",
        ["retention_until", "id"],
    )

    op.create_table(
        "intake_action_executions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("action_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column(
            "action_identifier",
            sa.String(64),
            nullable=False,
            server_default="contacts.intake.submit",
        ),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=True),
        sa.Column("submission_id", sa.BigInteger(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_intake_executions_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_intake_executions_workspace_revision",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_intake_executions_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_intake_executions_workspace_message",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_intake_executions_workspace_contact",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "lead_id"],
            ["leads.workspace_id", "leads.id"],
            name="fk_intake_executions_workspace_lead",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "submission_id"],
            ["contact_intake_submissions.workspace_id", "contact_intake_submissions.id"],
            name="fk_intake_executions_workspace_submission",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_intake_executions_workspace_id"),
        sa.UniqueConstraint("source_message_id", name="uq_intake_executions_source_message"),
        sa.UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_intake_executions_idempotency"
        ),
        sa.CheckConstraint(
            "action_identifier = 'contacts.intake.submit'",
            name="ck_intake_executions_action",
        ),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_intake_executions_hash"),
        sa.CheckConstraint(
            "state IN ('executing','succeeded','failed_retryable','failed_terminal')",
            name="ck_intake_executions_state",
        ),
        sa.CheckConstraint("replay_count >= 0", name="ck_intake_executions_replay_count"),
    )
    op.create_index(
        "ix_intake_action_executions_workspace_id",
        "intake_action_executions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_intake_executions_workspace_conversation",
        "intake_action_executions",
        ["workspace_id", "conversation_id", "created_at"],
    )
    op.create_index(
        "ix_intake_executions_retention",
        "intake_action_executions",
        ["retention_until", "id"],
    )


def downgrade() -> None:
    op.drop_table("intake_action_executions")
    op.drop_table("contact_intake_submissions")
    op.drop_index("ix_leads_workspace_qualification", table_name="leads")
    op.drop_constraint("ck_leads_qualification_version", "leads", type_="check")
    op.drop_constraint("ck_leads_qualification_status", "leads", type_="check")
    op.drop_column("leads", "qualification_updated_at")
    op.drop_column("leads", "qualification_updated_by_user_id")
    op.drop_column("leads", "qualification_reason")
    op.drop_column("leads", "qualification_version")
    op.drop_column("leads", "qualification_status")
    op.drop_column("agent_revisions", "intake_definition_json")
    op.drop_column("agent_revisions", "intake_action_enabled")
    op.drop_column("agents", "intake_definition_json")
    op.drop_column("agents", "intake_action_enabled")
