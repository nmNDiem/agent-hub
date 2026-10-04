"""Add scoped widget sessions and visitor conversations.

Revision ID: 20261004_0009
Revises: 20261003_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261004_0009"
down_revision: str | None = "20261003_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "widget_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("normalized_origin", sa.String(300), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_widget_sessions_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "channel_id"],
            ["agent_web_channels.workspace_id", "agent_web_channels.id"],
            name="fk_widget_sessions_workspace_channel",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            [
                "agent_revisions.workspace_id",
                "agent_revisions.agent_id",
                "agent_revisions.id",
            ],
            name="fk_widget_sessions_workspace_revision",
        ),
        sa.UniqueConstraint("token_hash", name="uq_widget_sessions_token_hash"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_widget_sessions_workspace_id"),
    )
    op.create_index("ix_widget_sessions_workspace_id", "widget_sessions", ["workspace_id"])
    op.create_index(
        "ix_widget_sessions_workspace_expiry",
        "widget_sessions",
        ["workspace_id", "expires_at", "id"],
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), server_default="open", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_conversations_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "session_id"],
            ["widget_sessions.workspace_id", "widget_sessions.id"],
            name="fk_conversations_workspace_session",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            [
                "agent_revisions.workspace_id",
                "agent_revisions.agent_id",
                "agent_revisions.id",
            ],
            name="fk_conversations_workspace_revision",
        ),
        sa.CheckConstraint("status IN ('open','deleted')", name="ck_conversations_status"),
        sa.UniqueConstraint("public_id", name="uq_conversations_public_id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_conversations_workspace_id"),
        sa.UniqueConstraint("session_id", name="uq_conversations_session"),
    )
    op.create_index("ix_conversations_workspace_id", "conversations", ["workspace_id"])
    op.create_index(
        "ix_conversations_workspace_last_message",
        "conversations",
        ["workspace_id", "last_message_at", "id"],
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request_key", sa.String(128), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("response_id", sa.Uuid(), nullable=True),
        sa.Column(
            "response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("safe_error_code", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("generation_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_messages_workspace_conversation",
        ),
        sa.CheckConstraint("actor IN ('visitor','assistant')", name="ck_messages_actor"),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed','cancelled')",
            name="ck_messages_status",
        ),
        sa.CheckConstraint("sequence_no > 0", name="ck_messages_sequence_positive"),
        sa.UniqueConstraint("response_id", name="uq_conversation_messages_response_id"),
        sa.UniqueConstraint("conversation_id", "sequence_no", name="uq_messages_sequence"),
        sa.UniqueConstraint("conversation_id", "request_key", name="uq_messages_request_key"),
    )
    op.create_index(
        "ix_conversation_messages_workspace_id", "conversation_messages", ["workspace_id"]
    )
    op.create_index(
        "ix_messages_workspace_conversation",
        "conversation_messages",
        ["workspace_id", "conversation_id", "id"],
    )
    op.create_index(
        "uq_messages_active_assistant",
        "conversation_messages",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("actor = 'assistant' AND status = 'pending'"),
    )

    op.create_table(
        "widget_rate_windows",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("count >= 0", name="ck_widget_rate_windows_count"),
        sa.UniqueConstraint(
            "workspace_id",
            "scope",
            "key_hash",
            "window_started_at",
            name="uq_widget_rate_windows_bucket",
        ),
    )
    op.create_index("ix_widget_rate_windows_workspace_id", "widget_rate_windows", ["workspace_id"])
    op.create_index(
        "ix_widget_rate_windows_expiry",
        "widget_rate_windows",
        ["window_started_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("widget_rate_windows")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_table("widget_sessions")
