"""Distinguish provider acceptance from Facebook delivery receipts.

Revision ID: 20261008_0015
Revises: 20261006_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261008_0015"
down_revision: str | None = "20261006_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_deliveries_state", "outbound_deliveries", type_="check")
    op.create_check_constraint(
        "ck_deliveries_state",
        "outbound_deliveries",
        "state IN ('queued','sending','accepted','delivered','failed_retryable','failed_terminal')",
    )
    op.add_column(
        "outbound_deliveries",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbound_deliveries",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE outbound_deliveries
        SET state = 'accepted', accepted_at = updated_at
        WHERE state = 'delivered'
        """
    )
    op.create_index(
        "ix_deliveries_connection_provider_message",
        "outbound_deliveries",
        ["connection_id", "provider_message_id"],
    )

    op.create_table(
        "channel_delivery_receipts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_message_id", sa.String(500), nullable=False),
        sa.Column("external_thread_id", sa.String(500), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_delivery_receipts_workspace_connection",
        ),
        sa.UniqueConstraint(
            "connection_id", "provider_message_id", name="uq_delivery_receipt_provider_message"
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_delivery_receipts_workspace_id"),
    )
    op.create_index(
        "ix_channel_delivery_receipts_workspace_id",
        "channel_delivery_receipts",
        ["workspace_id"],
    )
    op.create_index(
        "ix_delivery_receipts_workspace_connection",
        "channel_delivery_receipts",
        ["workspace_id", "connection_id", "received_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("channel_delivery_receipts")
    op.drop_index(
        "ix_deliveries_connection_provider_message", table_name="outbound_deliveries"
    )
    op.execute(
        """
        UPDATE outbound_deliveries
        SET state = 'delivered', updated_at = COALESCE(accepted_at, updated_at)
        WHERE state = 'accepted'
        """
    )
    op.drop_column("outbound_deliveries", "delivered_at")
    op.drop_column("outbound_deliveries", "accepted_at")
    op.drop_constraint("ck_deliveries_state", "outbound_deliveries", type_="check")
    op.create_check_constraint(
        "ck_deliveries_state",
        "outbound_deliveries",
        "state IN ('queued','sending','delivered','failed_retryable','failed_terminal')",
    )
