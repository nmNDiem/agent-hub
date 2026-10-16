"""Add Knowledge freshness review and recovery attribution.

Revision ID: 20261016_0021
Revises: 20261015_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0021"
down_revision: str | None = "20261015_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_document_versions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_document_versions",
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_document_versions",
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_document_versions_reviewer",
        "knowledge_document_versions",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_document_versions_workspace_review_due",
        "knowledge_document_versions",
        ["workspace_id", "review_due_at", "id"],
    )

    op.create_table(
        "knowledge_recovery_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('retry','rebuild')", name="ck_knowledge_recovery_events_action"
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0", name="ck_knowledge_recovery_events_reason_nonempty"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["ingestion_jobs.workspace_id", "ingestion_jobs.id"],
            name="fk_knowledge_recovery_events_workspace_job",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_knowledge_recovery_events_workspace_idempotency",
        ),
    )
    op.create_index(
        "ix_knowledge_recovery_events_workspace_id",
        "knowledge_recovery_events",
        ["workspace_id"],
    )
    op.create_index(
        "ix_knowledge_recovery_events_workspace_job_created",
        "knowledge_recovery_events",
        ["workspace_id", "job_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_table("knowledge_recovery_events")
    op.drop_index(
        "ix_document_versions_workspace_review_due",
        table_name="knowledge_document_versions",
    )
    op.drop_constraint(
        "fk_knowledge_document_versions_reviewer",
        "knowledge_document_versions",
        type_="foreignkey",
    )
    op.drop_column("knowledge_document_versions", "reviewed_by_user_id")
    op.drop_column("knowledge_document_versions", "review_due_at")
    op.drop_column("knowledge_document_versions", "reviewed_at")
