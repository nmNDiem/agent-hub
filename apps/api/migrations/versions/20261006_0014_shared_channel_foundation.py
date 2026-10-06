"""Add the shared channel and normalized conversation foundation.

Revision ID: 20261006_0014
Revises: 20261005_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0014"
down_revision: str | None = "20261005_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column[sa.DateTime], sa.Column[sa.DateTime]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "channel_connections",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=True),
        sa.Column("credential_ref", sa.String(500), nullable=True),
        sa.Column("lifecycle_state", sa.String(16), server_default="active", nullable=False),
        sa.Column("health_state", sa.String(16), server_default="unknown", nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "id", name="uq_channel_connections_workspace_id"),
        sa.UniqueConstraint(
            "provider", "external_account_id", name="uq_channel_connections_provider_account"
        ),
        sa.CheckConstraint("provider IN ('web','facebook','zalo')", name="ck_connections_provider"),
        sa.CheckConstraint(
            "lifecycle_state IN ('active','revoked')", name="ck_connections_lifecycle"
        ),
        sa.CheckConstraint(
            "health_state IN ('unknown','healthy','degraded','error')",
            name="ck_connections_health",
        ),
    )
    op.create_index(
        "ix_channel_connections_workspace_id", "channel_connections", ["workspace_id"]
    )
    op.create_index(
        "ix_connections_workspace_provider",
        "channel_connections",
        ["workspace_id", "provider", "id"],
    )
    op.execute(
        """
        INSERT INTO channel_connections
            (id, workspace_id, provider, display_name, lifecycle_state, health_state,
             created_at, updated_at)
        SELECT wc.id, wc.workspace_id, 'web', a.name, 'active',
               CASE WHEN wc.enabled THEN 'healthy' ELSE 'unknown' END,
               wc.created_at, wc.updated_at
        FROM agent_web_channels AS wc
        JOIN agents AS a ON a.workspace_id = wc.workspace_id AND a.id = wc.agent_id
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('channel_connections', 'id'),
            COALESCE((SELECT MAX(id) FROM channel_connections), 1),
            EXISTS (SELECT 1 FROM channel_connections)
        )
        """
    )

    op.create_table(
        "channel_agent_bindings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("active_revision_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_channel_bindings_workspace_connection",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_channel_bindings_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "active_revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_channel_bindings_workspace_revision",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_channel_bindings_workspace_id"),
        sa.UniqueConstraint("connection_id", name="uq_channel_bindings_connection"),
    )
    op.create_index(
        "ix_channel_agent_bindings_workspace_id", "channel_agent_bindings", ["workspace_id"]
    )
    op.create_index(
        "ix_channel_bindings_workspace_agent",
        "channel_agent_bindings",
        ["workspace_id", "agent_id", "enabled"],
    )
    op.execute(
        """
        INSERT INTO channel_agent_bindings
            (workspace_id, connection_id, agent_id, active_revision_id, enabled,
             created_at, updated_at)
        SELECT workspace_id, id, agent_id, active_revision_id, enabled, created_at, updated_at
        FROM agent_web_channels
        """
    )

    op.create_table(
        "website_channel_configs",
        sa.Column("connection_id", sa.BigInteger(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("brand_color", sa.String(7), server_default="#0F8F87", nullable=False),
        sa.Column("launcher_position", sa.String(8), server_default="right", nullable=False),
        sa.Column("handoff_url", sa.String(500), nullable=True),
        sa.Column("handoff_label", sa.String(80), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_website_configs_workspace_connection",
        ),
        sa.UniqueConstraint(
            "workspace_id", "connection_id", name="uq_website_configs_connection"
        ),
        sa.CheckConstraint(
            "launcher_position IN ('left','right')", name="ck_website_configs_launcher_position"
        ),
        sa.CheckConstraint(
            "length(brand_color) = 7", name="ck_website_configs_brand_color"
        ),
    )
    op.create_index(
        "ix_website_channel_configs_workspace_id", "website_channel_configs", ["workspace_id"]
    )
    op.execute(
        """
        INSERT INTO website_channel_configs
            (connection_id, workspace_id, brand_color, launcher_position, handoff_url,
             handoff_label, created_at, updated_at)
        SELECT id, workspace_id, brand_color, launcher_position, handoff_url,
               handoff_label, created_at, updated_at
        FROM agent_web_channels
        """
    )

    op.drop_constraint(
        "fk_widget_sessions_workspace_channel", "widget_sessions", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_widget_sessions_workspace_channel",
        "widget_sessions",
        "channel_connections",
        ["workspace_id", "channel_id"],
        ["workspace_id", "id"],
    )
    op.drop_constraint(
        "fk_widget_domains_workspace_channel", "widget_domains", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_widget_domains_workspace_channel",
        "widget_domains",
        "channel_connections",
        ["workspace_id", "channel_id"],
        ["workspace_id", "id"],
    )

    op.add_column("conversations", sa.Column("channel_connection_id", sa.BigInteger()))
    op.add_column(
        "conversations",
        sa.Column("workflow_status", sa.String(16), server_default="open", nullable=False),
    )
    op.add_column(
        "conversations",
        sa.Column("handling_mode", sa.String(16), server_default="ai", nullable=False),
    )
    op.execute(
        """
        UPDATE conversations AS c
        SET channel_connection_id = s.channel_id
        FROM widget_sessions AS s
        WHERE c.workspace_id = s.workspace_id AND c.session_id = s.id
        """
    )
    op.alter_column("conversations", "channel_connection_id", nullable=False)
    op.create_foreign_key(
        "fk_conversations_workspace_connection",
        "conversations",
        "channel_connections",
        ["workspace_id", "channel_connection_id"],
        ["workspace_id", "id"],
    )
    op.drop_constraint("ck_conversations_status", "conversations", type_="check")
    op.alter_column("conversations", "status", new_column_name="lifecycle_state")
    op.execute("UPDATE conversations SET lifecycle_state = 'active' WHERE lifecycle_state = 'open'")
    op.create_check_constraint(
        "ck_conversations_lifecycle",
        "conversations",
        "lifecycle_state IN ('active','deleted')",
    )
    op.create_check_constraint(
        "ck_conversations_workflow_status",
        "conversations",
        "workflow_status IN ('open','pending','resolved')",
    )
    op.create_check_constraint(
        "ck_conversations_handling_mode",
        "conversations",
        "handling_mode IN ('ai','human','paused')",
    )
    op.alter_column("conversations", "session_id", existing_type=sa.BigInteger(), nullable=True)
    op.create_index(
        "ix_conversations_workspace_connection",
        "conversations",
        ["workspace_id", "channel_connection_id", "id"],
    )

    op.add_column(
        "conversation_messages",
        sa.Column("direction", sa.String(16), server_default="inbound", nullable=False),
    )
    op.execute(
        "UPDATE conversation_messages SET direction = 'outbound' WHERE actor = 'assistant'"
    )
    op.alter_column("conversation_messages", "direction", server_default=None)
    op.drop_constraint("ck_messages_actor", "conversation_messages", type_="check")
    op.create_check_constraint(
        "ck_messages_actor",
        "conversation_messages",
        "actor IN ('visitor','assistant','human','tool','system')",
    )
    op.create_check_constraint(
        "ck_messages_direction",
        "conversation_messages",
        "direction IN ('inbound','outbound')",
    )
    op.create_unique_constraint(
        "uq_messages_workspace_id", "conversation_messages", ["workspace_id", "id"]
    )

    op.drop_table("agent_web_channels")
    _create_channel_work_tables()


def _create_channel_work_tables() -> None:
    op.create_table(
        "channel_thread_mappings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("external_thread_id", sa.String(500), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_thread_mappings_workspace_connection",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_thread_mappings_workspace_conversation",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_thread_mappings_workspace_id"),
        sa.UniqueConstraint("connection_id", "external_thread_id", name="uq_thread_external"),
        sa.UniqueConstraint("conversation_id", name="uq_thread_conversation"),
    )
    op.create_index(
        "ix_channel_thread_mappings_workspace_id", "channel_thread_mappings", ["workspace_id"]
    )
    op.create_index(
        "ix_thread_mappings_workspace_connection",
        "channel_thread_mappings",
        ["workspace_id", "connection_id", "id"],
    )

    op.create_table(
        "channel_message_mappings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=False),
        sa.Column("thread_mapping_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("external_message_id", sa.String(500), nullable=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_message_mappings_workspace_connection",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_message_mappings_workspace_message",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "thread_mapping_id"],
            ["channel_thread_mappings.workspace_id", "channel_thread_mappings.id"],
            name="fk_message_mappings_workspace_thread",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_message_mappings_workspace_id"),
        sa.UniqueConstraint("connection_id", "message_id", name="uq_message_mapping_message"),
        sa.UniqueConstraint(
            "connection_id", "external_message_id", name="uq_message_mapping_external"
        ),
        sa.CheckConstraint(
            "direction IN ('inbound','outbound')", name="ck_message_mapping_direction"
        ),
    )
    op.create_index(
        "ix_channel_message_mappings_workspace_id", "channel_message_mappings", ["workspace_id"]
    )
    op.create_index(
        "ix_message_mappings_workspace_connection",
        "channel_message_mappings",
        ["workspace_id", "connection_id", "id"],
    )

    op.create_table(
        "channel_webhook_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=False),
        sa.Column("external_event_id", sa.String(255), nullable=False),
        sa.Column("payload_fingerprint", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), server_default="received", nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("provider_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_webhook_events_workspace_connection",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_webhook_events_workspace_message",
        ),
        sa.UniqueConstraint(
            "connection_id", "external_event_id", name="uq_webhook_event_external"
        ),
        sa.CheckConstraint(
            "state IN ('received','processed','failed')", name="ck_webhook_events_state"
        ),
    )
    op.create_index(
        "ix_channel_webhook_events_workspace_id", "channel_webhook_events", ["workspace_id"]
    )
    op.create_index(
        "ix_webhook_events_processing",
        "channel_webhook_events",
        ["state", "received_at", "id"],
    )
    op.create_index(
        "ix_webhook_events_workspace_connection",
        "channel_webhook_events",
        ["workspace_id", "connection_id", "id"],
    )

    op.create_table(
        "outbound_deliveries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("state", sa.String(24), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_token", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(500), nullable=True),
        sa.Column("safe_error_code", sa.String(80), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_deliveries_workspace_connection",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_deliveries_workspace_message",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_deliveries_workspace_id"),
        sa.UniqueConstraint("connection_id", "idempotency_key", name="uq_delivery_idempotency"),
        sa.UniqueConstraint("connection_id", "message_id", name="uq_delivery_message"),
        sa.CheckConstraint(
            "state IN ('queued','sending','delivered','failed_retryable','failed_terminal')",
            name="ck_deliveries_state",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_deliveries_attempt_count"),
        sa.CheckConstraint("max_attempts > 0", name="ck_deliveries_max_attempts"),
    )
    op.create_index(
        "ix_outbound_deliveries_workspace_id", "outbound_deliveries", ["workspace_id"]
    )
    op.create_index(
        "ix_deliveries_claim",
        "outbound_deliveries",
        ["state", "next_attempt_at", "lease_expires_at", "id"],
    )
    op.create_index(
        "ix_deliveries_workspace_connection",
        "outbound_deliveries",
        ["workspace_id", "connection_id", "id"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM channel_connections WHERE provider <> 'web')
               OR EXISTS (SELECT 1 FROM conversations WHERE session_id IS NULL)
               OR EXISTS (
                    SELECT 1 FROM conversation_messages
                    WHERE actor NOT IN ('visitor','assistant')
               ) THEN
                RAISE EXCEPTION 'M1.1 downgrade requires Website-only channel data';
            END IF;
        END $$
        """
    )
    op.drop_table("outbound_deliveries")
    op.drop_table("channel_webhook_events")
    op.drop_table("channel_message_mappings")
    op.drop_table("channel_thread_mappings")

    op.create_table(
        "agent_web_channels",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("brand_color", sa.String(7), server_default="#0F8F87", nullable=False),
        sa.Column("launcher_position", sa.String(8), server_default="right", nullable=False),
        sa.Column("handoff_url", sa.String(500), nullable=True),
        sa.Column("handoff_label", sa.String(80), nullable=True),
        sa.Column("active_revision_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_web_channels_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id", "active_revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_web_channels_workspace_revision",
        ),
        sa.UniqueConstraint("workspace_id", "agent_id", name="uq_web_channels_workspace_agent"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_web_channels_workspace_id"),
        sa.CheckConstraint(
            "launcher_position IN ('left','right')", name="ck_web_channels_launcher_position"
        ),
        sa.CheckConstraint("length(brand_color) = 7", name="ck_web_channels_brand_color"),
    )
    op.create_index("ix_agent_web_channels_workspace_id", "agent_web_channels", ["workspace_id"])
    op.create_index(
        "ix_web_channels_workspace_enabled",
        "agent_web_channels",
        ["workspace_id", "enabled"],
    )
    op.execute(
        """
        INSERT INTO agent_web_channels
            (id, workspace_id, agent_id, brand_color, launcher_position, handoff_url,
             handoff_label, active_revision_id, enabled, created_at, updated_at)
        SELECT c.id, c.workspace_id, b.agent_id, w.brand_color, w.launcher_position,
               w.handoff_url, w.handoff_label, b.active_revision_id, b.enabled,
               c.created_at, c.updated_at
        FROM channel_connections AS c
        JOIN channel_agent_bindings AS b
          ON b.workspace_id = c.workspace_id AND b.connection_id = c.id
        JOIN website_channel_configs AS w
          ON w.workspace_id = c.workspace_id AND w.connection_id = c.id
        WHERE c.provider = 'web'
        """
    )
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('agent_web_channels', 'id'),
            COALESCE((SELECT MAX(id) FROM agent_web_channels), 1),
            EXISTS (SELECT 1 FROM agent_web_channels)
        )
        """
    )

    op.drop_constraint(
        "fk_widget_sessions_workspace_channel", "widget_sessions", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_widget_sessions_workspace_channel",
        "widget_sessions",
        "agent_web_channels",
        ["workspace_id", "channel_id"],
        ["workspace_id", "id"],
    )
    op.drop_constraint(
        "fk_widget_domains_workspace_channel", "widget_domains", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_widget_domains_workspace_channel",
        "widget_domains",
        "agent_web_channels",
        ["workspace_id", "channel_id"],
        ["workspace_id", "id"],
    )

    op.drop_constraint(
        "fk_conversations_workspace_connection", "conversations", type_="foreignkey"
    )
    op.drop_index("ix_conversations_workspace_connection", table_name="conversations")
    op.drop_constraint("ck_conversations_handling_mode", "conversations", type_="check")
    op.drop_constraint("ck_conversations_workflow_status", "conversations", type_="check")
    op.drop_constraint("ck_conversations_lifecycle", "conversations", type_="check")
    op.execute("UPDATE conversations SET lifecycle_state = 'open' WHERE lifecycle_state = 'active'")
    op.alter_column("conversations", "lifecycle_state", new_column_name="status")
    op.create_check_constraint(
        "ck_conversations_status", "conversations", "status IN ('open','deleted')"
    )
    op.alter_column("conversations", "session_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_column("conversations", "handling_mode")
    op.drop_column("conversations", "workflow_status")
    op.drop_column("conversations", "channel_connection_id")

    op.drop_constraint("uq_messages_workspace_id", "conversation_messages", type_="unique")
    op.drop_constraint("ck_messages_direction", "conversation_messages", type_="check")
    op.drop_constraint("ck_messages_actor", "conversation_messages", type_="check")
    op.create_check_constraint(
        "ck_messages_actor",
        "conversation_messages",
        "actor IN ('visitor','assistant')",
    )
    op.drop_column("conversation_messages", "direction")

    op.drop_table("website_channel_configs")
    op.drop_table("channel_agent_bindings")
    op.drop_table("channel_connections")
