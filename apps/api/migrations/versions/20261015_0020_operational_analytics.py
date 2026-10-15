"""Add persisted operational analytics facts and reporting indexes.

Revision ID: 20261015_0020
Revises: 20261014_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0020"
down_revision: str | None = "20261014_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_workspace_created",
        "conversation_messages",
        ["workspace_id", "created_at", "id"],
    )
    op.create_index(
        "ix_messages_workspace_completed",
        "conversation_messages",
        ["workspace_id", "completed_at", "id"],
    )
    op.create_index(
        "ix_conversation_audit_workspace_created",
        "conversation_audit_events",
        ["workspace_id", "created_at", "id"],
    )
    op.create_index(
        "ix_deliveries_workspace_created",
        "outbound_deliveries",
        ["workspace_id", "created_at", "id"],
    )
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("agent_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "channel IN ('web','facebook','zalo')", name="ck_analytics_events_channel"
        ),
        sa.CheckConstraint("event_type IN ('product_impression')", name="ck_analytics_events_type"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_analytics_events_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_analytics_events_workspace_conversation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_analytics_events_workspace_message",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_analytics_events_workspace_product",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "event_type",
            "message_id",
            "product_id",
            name="uq_analytics_events_message_product",
        ),
    )
    op.create_index("ix_analytics_events_workspace_id", "analytics_events", ["workspace_id"])
    op.create_index(
        "ix_analytics_events_workspace_time",
        "analytics_events",
        ["workspace_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_analytics_events_workspace_channel_time",
        "analytics_events",
        ["workspace_id", "channel", "occurred_at", "id"],
    )
    op.create_index(
        "ix_analytics_events_workspace_agent_time",
        "analytics_events",
        ["workspace_id", "agent_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_analytics_events_workspace_product_time",
        "analytics_events",
        ["workspace_id", "product_id", "occurred_at", "id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            INSERT INTO analytics_events
                (workspace_id, agent_id, conversation_id, message_id, product_id,
                 channel, event_type, occurred_at)
            SELECT m.workspace_id, c.agent_id, c.id, m.id, p.id,
                   cc.provider, 'product_impression', m.completed_at
            FROM conversation_messages m
            JOIN conversations c
              ON c.workspace_id = m.workspace_id AND c.id = m.conversation_id
            JOIN channel_connections cc
              ON cc.workspace_id = c.workspace_id AND cc.id = c.channel_connection_id
            CROSS JOIN LATERAL jsonb_array_elements(
                COALESCE(m.response_json::jsonb -> 'product_cards', '[]'::jsonb)
            ) AS card
            JOIN products p
              ON p.workspace_id = m.workspace_id
             AND p.id = (card ->> 'product_id')::bigint
            WHERE m.actor = 'assistant'
              AND m.status = 'completed'
              AND m.completed_at IS NOT NULL
            ON CONFLICT ON CONSTRAINT uq_analytics_events_message_product DO NOTHING
            """
        )


def downgrade() -> None:
    op.drop_table("analytics_events")
    op.drop_index("ix_deliveries_workspace_created", table_name="outbound_deliveries")
    op.drop_index("ix_conversation_audit_workspace_created", table_name="conversation_audit_events")
    op.drop_index("ix_messages_workspace_completed", table_name="conversation_messages")
    op.drop_index("ix_messages_workspace_created", table_name="conversation_messages")
