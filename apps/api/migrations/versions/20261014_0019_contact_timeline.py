"""Add consent-aware contacts and customer timeline.

Revision ID: 20261014_0019
Revises: 20261014_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_0019"
down_revision: str | None = "20261014_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("conversation_tags", "workspace_tags")

    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("assigned_member_id", sa.BigInteger(), nullable=True),
        sa.Column("lifecycle_state", sa.String(16), server_default="active", nullable=False),
        sa.Column("merged_into_contact_id", sa.BigInteger(), nullable=True),
        sa.Column("state_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ('active','expired','merged')", name="ck_contacts_lifecycle"
        ),
        sa.CheckConstraint("id <> merged_into_contact_id", name="ck_contacts_not_self_merged"),
        sa.UniqueConstraint("public_id", name="uq_contacts_public_id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_contacts_workspace_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "assigned_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contacts_workspace_assignee",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "merged_into_contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contacts_workspace_merge_target",
        ),
    )
    op.create_index("ix_contacts_workspace_id", "contacts", ["workspace_id"])
    op.create_index(
        "ix_contacts_workspace_list",
        "contacts",
        ["workspace_id", "lifecycle_state", "assigned_member_id", "updated_at", "public_id"],
    )
    op.create_index("ix_contacts_retention", "contacts", ["retention_until", "id"])

    # A Website lead owns one conversation, so its existing UUIDv7 is a stable UUIDv7 contact ID.
    op.execute(
        """
        INSERT INTO contacts
            (public_id, workspace_id, display_name, lifecycle_state, state_version,
             retention_until, created_at, updated_at)
        SELECT c.public_id, l.workspace_id, l.name, 'active', 1,
               l.retention_until, l.created_at, l.updated_at
        FROM leads l
        JOIN conversations c
          ON c.workspace_id = l.workspace_id AND c.id = l.conversation_id
        """
    )
    # Existing social threads become distinct contacts. Provider identities are not cross-linked.
    op.execute(
        """
        INSERT INTO contacts
            (public_id, workspace_id, display_name, lifecycle_state, state_version,
             retention_until, created_at, updated_at)
        SELECT c.public_id, c.workspace_id, NULL, 'active', 1,
               c.retention_until, c.created_at, c.created_at
        FROM conversations c
        JOIN channel_connections cc
          ON cc.workspace_id = c.workspace_id AND cc.id = c.channel_connection_id
        WHERE cc.provider IN ('facebook', 'zalo')
          AND NOT EXISTS (SELECT 1 FROM contacts existing WHERE existing.public_id = c.public_id)
        """
    )

    op.add_column("conversations", sa.Column("contact_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_conversations_workspace_contact",
        "conversations",
        "contacts",
        ["workspace_id", "contact_id"],
        ["workspace_id", "id"],
    )
    op.create_index(
        "ix_conversations_workspace_contact", "conversations", ["workspace_id", "contact_id", "id"]
    )
    op.execute(
        """
        UPDATE conversations c
        SET contact_id = contact.id
        FROM contacts contact
        WHERE contact.workspace_id = c.workspace_id AND contact.public_id = c.public_id
        """
    )

    op.add_column("leads", sa.Column("contact_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_leads_workspace_contact",
        "leads",
        "contacts",
        ["workspace_id", "contact_id"],
        ["workspace_id", "id"],
    )
    op.create_index("ix_leads_workspace_contact", "leads", ["workspace_id", "contact_id", "id"])
    op.execute(
        """
        UPDATE leads l
        SET contact_id = c.contact_id
        FROM conversations c
        WHERE c.workspace_id = l.workspace_id AND c.id = l.conversation_id
        """
    )
    op.alter_column("leads", "contact_id", existing_type=sa.BigInteger(), nullable=False)

    op.create_table(
        "contact_identities",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("connection_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("identity_type", sa.String(16), nullable=False),
        sa.Column("normalized_value", sa.String(512), nullable=False),
        sa.Column("verification_state", sa.String(24), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_text_version", sa.String(80), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "provider IN ('website','facebook','zalo')", name="ck_contact_identities_provider"
        ),
        sa.CheckConstraint(
            "identity_type IN ('email','phone','channel')", name="ck_contact_identities_type"
        ),
        sa.CheckConstraint(
            "verification_state IN ('consented','provider_asserted')",
            name="ck_contact_identities_verification",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_identities_workspace_contact",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_contact_identities_workspace_connection",
        ),
        sa.UniqueConstraint(
            "contact_id",
            "provider",
            "identity_type",
            "normalized_value",
            name="uq_contact_identities_contact_value",
        ),
    )
    op.create_index("ix_contact_identities_workspace_id", "contact_identities", ["workspace_id"])
    op.create_index(
        "ix_contact_identities_duplicate",
        "contact_identities",
        ["workspace_id", "identity_type", "normalized_value", "contact_id"],
    )
    op.create_index(
        "uq_contact_identities_channel",
        "contact_identities",
        ["workspace_id", "connection_id", "normalized_value"],
        unique=True,
        postgresql_where=sa.text("connection_id IS NOT NULL"),
        sqlite_where=sa.text("connection_id IS NOT NULL"),
    )
    op.execute(
        """
        INSERT INTO contact_identities
            (workspace_id, contact_id, connection_id, provider, identity_type, normalized_value,
             verification_state, consent_at, consent_text_version, retention_until, created_at)
        SELECT workspace_id, contact_id, NULL, 'website', 'email', normalized_email,
               'consented', consent_at, consent_text_version, retention_until, created_at
        FROM leads WHERE normalized_email IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO contact_identities
            (workspace_id, contact_id, connection_id, provider, identity_type, normalized_value,
             verification_state, consent_at, consent_text_version, retention_until, created_at)
        SELECT workspace_id, contact_id, NULL, 'website', 'phone', phone,
               'consented', consent_at, consent_text_version, retention_until, created_at
        FROM leads WHERE phone IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO contact_identities
            (workspace_id, contact_id, connection_id, provider, identity_type, normalized_value,
             verification_state, consent_at, consent_text_version, retention_until, created_at)
        SELECT c.workspace_id, c.contact_id, tm.connection_id, cc.provider, 'channel',
               tm.external_thread_id, 'provider_asserted', NULL, NULL,
               c.retention_until, c.created_at
        FROM conversations c
        JOIN channel_thread_mappings tm
          ON tm.workspace_id = c.workspace_id AND tm.conversation_id = c.id
        JOIN channel_connections cc
          ON cc.workspace_id = tm.workspace_id AND cc.id = tm.connection_id
        WHERE c.contact_id IS NOT NULL AND cc.provider IN ('facebook', 'zalo')
        """
    )

    op.create_table(
        "contact_notes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("author_member_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_notes_workspace_contact",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "author_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contact_notes_workspace_author",
        ),
    )
    op.create_index("ix_contact_notes_workspace_id", "contact_notes", ["workspace_id"])
    op.create_index(
        "ix_contact_notes_workspace_contact", "contact_notes", ["workspace_id", "contact_id", "id"]
    )

    op.create_table(
        "contact_tag_links",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_tag_links_workspace_contact",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "tag_id"],
            ["workspace_tags.workspace_id", "workspace_tags.id"],
            name="fk_contact_tag_links_workspace_tag",
        ),
        sa.UniqueConstraint("contact_id", "tag_id", name="uq_contact_tag_links_pair"),
    )
    op.create_index("ix_contact_tag_links_workspace_id", "contact_tag_links", ["workspace_id"])

    op.create_table(
        "contact_audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_member_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("details_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_audit_workspace_contact",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "actor_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contact_audit_workspace_actor",
        ),
    )
    op.create_index("ix_contact_audit_workspace_id", "contact_audit_events", ["workspace_id"])
    op.create_index(
        "ix_contact_audit_workspace_contact",
        "contact_audit_events",
        ["workspace_id", "contact_id", "id"],
    )

    op.create_table(
        "contact_merge_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("source_contact_id", sa.BigInteger(), nullable=False),
        sa.Column("target_contact_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_member_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("reversed_by_member_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_contact_id <> target_contact_id", name="ck_contact_merges_distinct"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_merges_workspace_source",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "target_contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_merges_workspace_target",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "actor_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contact_merges_workspace_actor",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "reversed_by_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contact_merges_workspace_reverser",
        ),
    )
    op.create_index("ix_contact_merges_workspace_id", "contact_merge_events", ["workspace_id"])
    op.create_index(
        "ix_contact_merges_workspace_source",
        "contact_merge_events",
        ["workspace_id", "source_contact_id", "id"],
    )


def downgrade() -> None:
    op.drop_table("contact_merge_events")
    op.drop_table("contact_audit_events")
    op.drop_table("contact_tag_links")
    op.drop_table("contact_notes")
    op.drop_table("contact_identities")
    op.drop_index("ix_leads_workspace_contact", table_name="leads")
    op.drop_constraint("fk_leads_workspace_contact", "leads", type_="foreignkey")
    op.drop_column("leads", "contact_id")
    op.drop_index("ix_conversations_workspace_contact", table_name="conversations")
    op.drop_constraint("fk_conversations_workspace_contact", "conversations", type_="foreignkey")
    op.drop_column("conversations", "contact_id")
    op.drop_table("contacts")
    op.rename_table("workspace_tags", "conversation_tags")
