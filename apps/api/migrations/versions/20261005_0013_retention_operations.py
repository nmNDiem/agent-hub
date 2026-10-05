"""Add retryable visitor-image cleanup and retention-safe usage links.

Revision ID: 20261005_0013
Revises: 20261004_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0013"
down_revision: str | None = "20261004_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "visitor_image_uploads",
        sa.Column("cleanup_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "visitor_image_uploads",
        sa.Column("last_cleanup_error", sa.String(length=80), nullable=True),
    )
    op.create_check_constraint(
        "ck_visitor_images_cleanup_attempts",
        "visitor_image_uploads",
        "cleanup_attempts >= 0",
    )
    op.create_index(
        "ix_visitor_images_cleanup",
        "visitor_image_uploads",
        ["status", "expires_at", "id"],
    )
    op.drop_constraint(
        "fk_usage_events_workspace_conversation",
        "usage_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_usage_events_workspace_conversation",
        "usage_events",
        "conversations",
        ["workspace_id", "conversation_id"],
        ["workspace_id", "id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_usage_events_workspace_conversation",
        "usage_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_usage_events_workspace_conversation",
        "usage_events",
        "conversations",
        ["workspace_id", "conversation_id"],
        ["workspace_id", "id"],
    )
    op.drop_index("ix_visitor_images_cleanup", table_name="visitor_image_uploads")
    op.drop_constraint(
        "ck_visitor_images_cleanup_attempts",
        "visitor_image_uploads",
        type_="check",
    )
    op.drop_column("visitor_image_uploads", "last_cleanup_error")
    op.drop_column("visitor_image_uploads", "cleanup_attempts")
