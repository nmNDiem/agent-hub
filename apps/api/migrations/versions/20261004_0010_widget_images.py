"""Add private visitor image uploads.

Revision ID: 20261004_0010
Revises: 20261004_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261004_0010"
down_revision: str | None = "20261004_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visitor_image_uploads",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("attached_conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("attached_request_key", sa.String(128), nullable=True),
        sa.Column("object_key", sa.String(900), nullable=True),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), server_default="uploading", nullable=False),
        sa.Column(
            "analysis_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "session_id"],
            ["widget_sessions.workspace_id", "widget_sessions.id"],
            name="fk_visitor_images_workspace_session",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "attached_conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_visitor_images_workspace_conversation",
        ),
        sa.CheckConstraint(
            "status IN ('uploading','available','attached','cleanup_pending','deleted')",
            name="ck_visitor_images_status",
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_visitor_images_byte_size"),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name="ck_visitor_images_dimensions"
        ),
        sa.UniqueConstraint("public_id", name="uq_visitor_image_uploads_public_id"),
        sa.UniqueConstraint("object_key", name="uq_visitor_image_uploads_object_key"),
    )
    op.create_index(
        "ix_visitor_image_uploads_workspace_id",
        "visitor_image_uploads",
        ["workspace_id"],
    )
    op.create_index(
        "ix_visitor_images_workspace_session_expiry",
        "visitor_image_uploads",
        ["workspace_id", "session_id", "expires_at", "id"],
    )

    op.create_table(
        "widget_catalog_image_grants",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("product_image_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "session_id"],
            ["widget_sessions.workspace_id", "widget_sessions.id"],
            name="fk_widget_image_grants_workspace_session",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "product_image_id"],
            ["product_images.workspace_id", "product_images.id"],
            name="fk_widget_image_grants_workspace_image",
        ),
        sa.UniqueConstraint("public_id", name="uq_widget_catalog_image_grants_public_id"),
        sa.UniqueConstraint(
            "session_id",
            "product_image_id",
            name="uq_widget_image_grants_session_image",
        ),
    )
    op.create_index(
        "ix_widget_catalog_image_grants_workspace_id",
        "widget_catalog_image_grants",
        ["workspace_id"],
    )
    op.create_index(
        "ix_widget_image_grants_workspace_expiry",
        "widget_catalog_image_grants",
        ["workspace_id", "expires_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("widget_catalog_image_grants")
    op.drop_table("visitor_image_uploads")
