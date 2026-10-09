"""Add Facebook response jobs, media quarantine and thread policy.

Revision ID: 20261008_0016
Revises: 20261008_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261008_0016"
down_revision: str | None = "20261008_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_usage_surface", "usage_events", type_="check")
    op.create_check_constraint(
        "ck_usage_surface",
        "usage_events",
        "surface IN ('widget','playground','facebook')",
    )
    op.drop_constraint("ck_connections_health", "channel_connections", type_="check")
    op.execute(
        "UPDATE channel_connections SET health_state = 'reauth_required' "
        "WHERE health_state IN ('degraded', 'error')"
    )
    op.create_check_constraint(
        "ck_connections_health",
        "channel_connections",
        "health_state IN ('unknown','healthy','permission_expired','reauth_required',"
        "'webhook_subscription_failure','delivery_unknown')",
    )

    op.add_column(
        "channel_thread_mappings",
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "channel_thread_mappings",
        sa.Column("automation_state", sa.String(16), server_default="opted_in", nullable=False),
    )
    op.execute(
        "UPDATE channel_thread_mappings SET last_inbound_at = last_seen_at "
        "WHERE last_inbound_at IS NULL"
    )
    op.create_check_constraint(
        "ck_thread_mappings_automation",
        "channel_thread_mappings",
        "automation_state IN ('opted_in','opted_out')",
    )

    op.create_table(
        "channel_response_jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("inbound_message_id", sa.BigInteger(), nullable=False),
        sa.Column("outbound_message_id", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(24), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_token", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_response_jobs_workspace_connection",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_response_jobs_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "inbound_message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_response_jobs_workspace_inbound_message",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "outbound_message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_response_jobs_workspace_outbound_message",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_response_jobs_workspace_id"),
        sa.UniqueConstraint("inbound_message_id", name="uq_response_jobs_inbound_message"),
        sa.CheckConstraint(
            "state IN ('queued','running','completed','failed_retryable',"
            "'failed_terminal','suppressed')",
            name="ck_response_jobs_state",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_response_jobs_attempt_count"),
        sa.CheckConstraint("max_attempts > 0", name="ck_response_jobs_max_attempts"),
    )
    op.create_index("ix_response_jobs_workspace_id", "channel_response_jobs", ["workspace_id"])
    op.create_index(
        "ix_response_jobs_claim",
        "channel_response_jobs",
        ["state", "next_attempt_at", "lease_expires_at", "id"],
    )
    op.create_index(
        "ix_response_jobs_workspace_connection",
        "channel_response_jobs",
        ["workspace_id", "connection_id", "id"],
    )

    op.create_table(
        "channel_inbound_media",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_media_id", sa.String(500), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("state", sa.String(24), server_default="pending", nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("object_key", sa.String(1024), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_inbound_media_workspace_connection",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_inbound_media_workspace_message",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_inbound_media_workspace_id"),
        sa.UniqueConstraint(
            "connection_id", "provider_media_id", name="uq_inbound_media_provider_id"
        ),
        sa.CheckConstraint(
            "kind IN ('image','audio','video','file')", name="ck_inbound_media_kind"
        ),
        sa.CheckConstraint(
            "state IN ('pending','available','unsupported','cleanup_pending','deleted','failed')",
            name="ck_inbound_media_state",
        ),
        sa.CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="ck_inbound_media_bytes"),
    )
    op.create_index("ix_inbound_media_workspace_id", "channel_inbound_media", ["workspace_id"])
    op.create_index(
        "ix_inbound_media_cleanup", "channel_inbound_media", ["state", "expires_at", "id"]
    )
    op.create_index(
        "ix_inbound_media_workspace_message",
        "channel_inbound_media",
        ["workspace_id", "message_id", "id"],
    )


def downgrade() -> None:
    op.execute("DELETE FROM usage_events WHERE surface = 'facebook'")
    op.drop_constraint("ck_usage_surface", "usage_events", type_="check")
    op.create_check_constraint(
        "ck_usage_surface",
        "usage_events",
        "surface IN ('widget','playground')",
    )
    op.drop_table("channel_inbound_media")
    op.drop_table("channel_response_jobs")
    op.drop_constraint("ck_thread_mappings_automation", "channel_thread_mappings", type_="check")
    op.drop_column("channel_thread_mappings", "automation_state")
    op.drop_column("channel_thread_mappings", "last_inbound_at")
    op.drop_constraint("ck_connections_health", "channel_connections", type_="check")
    op.execute(
        "UPDATE channel_connections SET health_state = 'error' "
        "WHERE health_state NOT IN ('unknown', 'healthy')"
    )
    op.create_check_constraint(
        "ck_connections_health",
        "channel_connections",
        "health_state IN ('unknown','healthy','degraded','error')",
    )
