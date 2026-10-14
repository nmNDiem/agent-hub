"""Add unified inbox workflow state.

Revision ID: 20261014_0018
Revises: 20261014_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0018"
down_revision: str | None = "20261014_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_workspace_members_workspace_id", "workspace_members", ["workspace_id", "id"]
    )
    op.add_column("conversations", sa.Column("assigned_member_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("state_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_foreign_key(
        "fk_conversations_workspace_assignee",
        "conversations",
        "workspace_members",
        ["workspace_id", "assigned_member_id"],
        ["workspace_id", "id"],
    )
    op.create_index(
        "ix_conversations_workspace_inbox",
        "conversations",
        ["workspace_id", "workflow_status", "assigned_member_id", "last_message_at", "id"],
    )

    op.create_table(
        "conversation_read_states",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.Column("last_read_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_reads_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_conversation_reads_workspace_member",
        ),
        sa.UniqueConstraint("conversation_id", "member_id", name="uq_conversation_reads_member"),
    )
    op.create_index(
        "ix_conversation_read_states_workspace_id", "conversation_read_states", ["workspace_id"]
    )
    op.create_index(
        "ix_conversation_reads_workspace_member",
        "conversation_read_states",
        ["workspace_id", "member_id"],
    )

    op.create_table(
        "conversation_notes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("author_member_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_notes_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "author_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_conversation_notes_workspace_author",
        ),
    )
    op.create_index("ix_conversation_notes_workspace_id", "conversation_notes", ["workspace_id"])
    op.create_index(
        "ix_conversation_notes_workspace_conversation",
        "conversation_notes",
        ["workspace_id", "conversation_id", "id"],
    )

    op.create_table(
        "conversation_tags",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(48), nullable=False),
        sa.Column("normalized_name", sa.String(48), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_conversation_tags_workspace_id"),
        sa.UniqueConstraint("workspace_id", "normalized_name", name="uq_conversation_tags_name"),
    )
    op.create_index("ix_conversation_tags_workspace_id", "conversation_tags", ["workspace_id"])
    op.create_index(
        "ix_conversation_tags_workspace_name",
        "conversation_tags",
        ["workspace_id", "normalized_name"],
    )

    op.create_table(
        "conversation_tag_links",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_tag_links_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "tag_id"],
            ["conversation_tags.workspace_id", "conversation_tags.id"],
            name="fk_conversation_tag_links_workspace_tag",
        ),
        sa.UniqueConstraint("conversation_id", "tag_id", name="uq_conversation_tag_links_pair"),
    )
    op.create_index(
        "ix_conversation_tag_links_workspace_id", "conversation_tag_links", ["workspace_id"]
    )
    op.create_index(
        "ix_conversation_tag_links_workspace_tag",
        "conversation_tag_links",
        ["workspace_id", "tag_id", "conversation_id"],
    )

    op.create_table(
        "conversation_audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_member_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("details_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_conversation_audit_workspace_conversation",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "actor_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_conversation_audit_workspace_actor",
        ),
    )
    op.create_index(
        "ix_conversation_audit_events_workspace_id", "conversation_audit_events", ["workspace_id"]
    )
    op.create_index(
        "ix_conversation_audit_workspace_conversation",
        "conversation_audit_events",
        ["workspace_id", "conversation_id", "id"],
    )


def downgrade() -> None:
    op.drop_table("conversation_audit_events")
    op.drop_table("conversation_tag_links")
    op.drop_table("conversation_tags")
    op.drop_table("conversation_notes")
    op.drop_table("conversation_read_states")
    op.drop_index("ix_conversations_workspace_inbox", table_name="conversations")
    op.drop_constraint("fk_conversations_workspace_assignee", "conversations", type_="foreignkey")
    op.drop_column("conversations", "state_version")
    op.drop_column("conversations", "assigned_member_id")
    op.drop_constraint("uq_workspace_members_workspace_id", "workspace_members", type_="unique")
