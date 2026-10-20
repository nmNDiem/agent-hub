from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "assigned_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contacts_workspace_assignee",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "merged_into_contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contacts_workspace_merge_target",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_contacts_workspace_id"),
        CheckConstraint(
            "lifecycle_state IN ('active','expired','merged')", name="ck_contacts_lifecycle"
        ),
        CheckConstraint("id <> merged_into_contact_id", name="ck_contacts_not_self_merged"),
        Index(
            "ix_contacts_workspace_list",
            "workspace_id",
            "lifecycle_state",
            "assigned_member_id",
            "updated_at",
            "public_id",
        ),
        Index("ix_contacts_retention", "retention_until", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    public_id: Mapped[UUID] = mapped_column(unique=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_member_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(16), default="active")
    merged_into_contact_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    state_version: Mapped[int] = mapped_column(Integer(), default=1)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ContactIdentity(Base):
    __tablename__ = "contact_identities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_identities_workspace_contact",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "connection_id"],
            ["channel_connections.workspace_id", "channel_connections.id"],
            name="fk_contact_identities_workspace_connection",
        ),
        UniqueConstraint(
            "contact_id",
            "provider",
            "identity_type",
            "normalized_value",
            name="uq_contact_identities_contact_value",
        ),
        CheckConstraint(
            "provider IN ('website','facebook','zalo')", name="ck_contact_identities_provider"
        ),
        CheckConstraint(
            "identity_type IN ('email','phone','channel')", name="ck_contact_identities_type"
        ),
        CheckConstraint(
            "verification_state IN ('consented','provider_asserted')",
            name="ck_contact_identities_verification",
        ),
        Index(
            "ix_contact_identities_duplicate",
            "workspace_id",
            "identity_type",
            "normalized_value",
            "contact_id",
        ),
        Index(
            "uq_contact_identities_channel",
            "workspace_id",
            "connection_id",
            "normalized_value",
            unique=True,
            postgresql_where=text("connection_id IS NOT NULL"),
            sqlite_where=text("connection_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    contact_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    connection_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    provider: Mapped[str] = mapped_column(String(16))
    identity_type: Mapped[str] = mapped_column(String(16))
    normalized_value: Mapped[str] = mapped_column(String(512))
    verification_state: Mapped[str] = mapped_column(String(24))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_text_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FollowUpActionExecution(Base):
    __tablename__ = "follow_up_action_executions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_follow_up_executions_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "agent_id", "revision_id"],
            ["agent_revisions.workspace_id", "agent_revisions.agent_id", "agent_revisions.id"],
            name="fk_follow_up_executions_workspace_revision",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            name="fk_follow_up_executions_workspace_conversation",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_message_id"],
            ["conversation_messages.workspace_id", "conversation_messages.id"],
            name="fk_follow_up_executions_workspace_message",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_follow_up_executions_workspace_contact",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "lead_id"],
            ["leads.workspace_id", "leads.id"],
            name="fk_follow_up_executions_workspace_lead",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_follow_up_executions_workspace_id"),
        UniqueConstraint("source_message_id", name="uq_follow_up_executions_source_message"),
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_follow_up_executions_idempotency"
        ),
        CheckConstraint(
            "action_identifier = 'contacts.follow_up.request'",
            name="ck_follow_up_executions_action",
        ),
        CheckConstraint("length(request_hash) = 64", name="ck_follow_up_executions_hash"),
        CheckConstraint(
            "state IN ('executing','succeeded','failed_retryable','failed_terminal')",
            name="ck_follow_up_executions_state",
        ),
        CheckConstraint("replay_count >= 0", name="ck_follow_up_executions_replay_count"),
        Index(
            "ix_follow_up_executions_workspace_conversation",
            "workspace_id",
            "conversation_id",
            "created_at",
        ),
        Index("ix_follow_up_executions_retention", "retention_until", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    action_id: Mapped[UUID] = mapped_column(unique=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    action_identifier: Mapped[str] = mapped_column(
        String(64), default="contacts.follow_up.request"
    )
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    revision_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    conversation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    source_message_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    contact_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    lead_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24), default="executing")
    safe_outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    replay_count: Mapped[int] = mapped_column(Integer(), default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContactNote(Base):
    __tablename__ = "contact_notes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_notes_workspace_contact",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "author_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contact_notes_workspace_author",
        ),
        Index("ix_contact_notes_workspace_contact", "workspace_id", "contact_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    contact_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    author_member_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    body: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContactTagLink(Base):
    __tablename__ = "contact_tag_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_tag_links_workspace_contact",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "tag_id"],
            ["workspace_tags.workspace_id", "workspace_tags.id"],
            name="fk_contact_tag_links_workspace_tag",
        ),
        UniqueConstraint("contact_id", "tag_id", name="uq_contact_tag_links_pair"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    contact_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    tag_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContactAuditEvent(Base):
    __tablename__ = "contact_audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_audit_workspace_contact",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "actor_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contact_audit_workspace_actor",
        ),
        Index("ix_contact_audit_workspace_contact", "workspace_id", "contact_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    contact_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    actor_member_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    event_type: Mapped[str] = mapped_column(String(40))
    details_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ContactMergeEvent(Base):
    __tablename__ = "contact_merge_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "source_contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_merges_workspace_source",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "target_contact_id"],
            ["contacts.workspace_id", "contacts.id"],
            name="fk_contact_merges_workspace_target",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "actor_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contact_merges_workspace_actor",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "reversed_by_member_id"],
            ["workspace_members.workspace_id", "workspace_members.id"],
            name="fk_contact_merges_workspace_reverser",
        ),
        CheckConstraint(
            "source_contact_id <> target_contact_id", name="ck_contact_merges_distinct"
        ),
        Index("ix_contact_merges_workspace_source", "workspace_id", "source_contact_id", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    source_contact_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    target_contact_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    actor_member_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    reason: Mapped[str] = mapped_column(String(240))
    reversed_by_member_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
