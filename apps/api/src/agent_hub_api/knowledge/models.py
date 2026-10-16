from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
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


class EmbeddingProfile(Base):
    __tablename__ = "embedding_profiles"
    __table_args__ = (
        CheckConstraint("dimensions > 0", name="ck_embedding_profiles_dimensions"),
        CheckConstraint(
            "distance_metric IN ('cosine','dot','euclid')",
            name="ck_embedding_profiles_distance_metric",
        ),
        CheckConstraint(
            "status IN ('building','active','deprecated','failed')",
            name="ck_embedding_profiles_status",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(200))
    dimensions: Mapped[int] = mapped_column(Integer())
    provider_model_revision: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pipeline_version: Mapped[str] = mapped_column(String(64))
    distance_metric: Mapped[str] = mapped_column(String(16))
    qdrant_collection: Mapped[str] = mapped_column(String(200), unique=True)
    config_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="building")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_knowledge_bases_workspace_id_id"),
        CheckConstraint("length(trim(name)) > 0", name="ck_knowledge_bases_name_nonempty"),
        CheckConstraint(
            "kind IN ('shop','faq','policy','general')", name="ck_knowledge_bases_kind"
        ),
        CheckConstraint("status IN ('active','archived')", name="ck_knowledge_bases_status"),
        Index(
            "ix_knowledge_bases_workspace_status_created",
            "workspace_id",
            "status",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(24), default="general")
    status: Mapped[str] = mapped_column(String(16), default="active")
    active_embedding_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("embedding_profiles.id"), nullable=True
    )
    target_embedding_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("embedding_profiles.id"), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AgentKnowledgeBase(Base):
    __tablename__ = "agent_knowledge_bases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_agent_knowledge_bases_workspace_agent",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "knowledge_base_id"],
            ["knowledge_bases.workspace_id", "knowledge_bases.id"],
            name="fk_agent_knowledge_bases_workspace_base",
        ),
        Index(
            "ix_agent_knowledge_bases_workspace_base", "workspace_id", "knowledge_base_id"
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    agent_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_media_assets_workspace_id_id"),
        CheckConstraint("byte_size >= 0", name="ck_media_assets_byte_size"),
        CheckConstraint("visibility = 'private'", name="ck_media_assets_private"),
        CheckConstraint(
            "status IN ('reserved','available','delete_pending','deleted','failed')",
            name="ck_media_assets_status",
        ),
        Index("ix_media_assets_workspace_status", "workspace_id", "status", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    bucket: Mapped[str] = mapped_column(String(120))
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(120))
    byte_size: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    sha256: Mapped[str] = mapped_column(String(64))
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    status: Mapped[str] = mapped_column(String(24), default="reserved")
    cleanup_attempts: Mapped[int] = mapped_column(Integer(), default=0)
    deletion_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_knowledge_documents_workspace_id_id"),
        ForeignKeyConstraint(
            ["workspace_id", "knowledge_base_id"],
            ["knowledge_bases.workspace_id", "knowledge_bases.id"],
            name="fk_knowledge_documents_workspace_base",
        ),
        CheckConstraint(
            "kind IN ('profile','faq','policy','size_guidance','document')",
            name="ck_knowledge_documents_kind",
        ),
        CheckConstraint(
            "status IN ('active','deleted')", name="ck_knowledge_documents_status"
        ),
        Index(
            "ix_knowledge_documents_workspace_base_status",
            "workspace_id",
            "knowledge_base_id",
            "status",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    knowledge_base_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    title: Mapped[str] = mapped_column(String(240))
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class KnowledgeDocumentVersion(Base):
    __tablename__ = "knowledge_document_versions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "id", name="uq_knowledge_document_versions_workspace_id_id"
        ),
        UniqueConstraint(
            "workspace_id",
            "document_id",
            "id",
            name="uq_document_versions_workspace_document_id",
        ),
        UniqueConstraint("document_id", "version_no", name="uq_document_versions_number"),
        ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
            name="fk_document_versions_workspace_document",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "media_asset_id"],
            ["media_assets.workspace_id", "media_assets.id"],
            name="fk_document_versions_workspace_asset",
        ),
        CheckConstraint("version_no > 0", name="ck_document_versions_number"),
        CheckConstraint(
            "source_kind IN ('manual','file')", name="ck_document_versions_source_kind"
        ),
        CheckConstraint(
            "(source_kind = 'manual' AND source_text IS NOT NULL AND media_asset_id IS NULL) OR "
            "(source_kind = 'file' AND source_text IS NULL AND media_asset_id IS NOT NULL)",
            name="ck_document_versions_source",
        ),
        Index(
            "ix_document_versions_workspace_document",
            "workspace_id",
            "document_id",
            "version_no",
        ),
        Index(
            "ix_document_versions_workspace_review_due",
            "workspace_id",
            "review_due_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    version_no: Mapped[int] = mapped_column(Integer())
    source_kind: Mapped[str] = mapped_column(String(16))
    source_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    media_asset_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    content_sha256: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str] = mapped_column(String(120))
    byte_size: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", name="fk_knowledge_document_versions_reviewer"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeGeneration(Base):
    __tablename__ = "knowledge_generations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_knowledge_generations_workspace_id_id"),
        UniqueConstraint(
            "workspace_id",
            "document_id",
            "id",
            name="uq_generations_workspace_document_id",
        ),
        UniqueConstraint("document_id", "generation_no", name="uq_generations_document_number"),
        ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
            name="fk_generations_workspace_document",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "document_id", "document_version_id"],
            [
                "knowledge_document_versions.workspace_id",
                "knowledge_document_versions.document_id",
                "knowledge_document_versions.id",
            ],
            name="fk_generations_workspace_version",
        ),
        CheckConstraint("generation_no > 0", name="ck_generations_number"),
        CheckConstraint(
            "status IN ('building','ready','failed','revoked')", name="ck_generations_status"
        ),
        CheckConstraint("chunk_size > 0", name="ck_generations_chunk_size"),
        CheckConstraint(
            "chunk_overlap >= 0 AND chunk_overlap < chunk_size",
            name="ck_generations_chunk_overlap",
        ),
        Index(
            "ix_generations_workspace_document_status",
            "workspace_id",
            "document_id",
            "status",
            "generation_no",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    document_version_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    embedding_profile_id: Mapped[int] = mapped_column(ForeignKey("embedding_profiles.id"))
    generation_no: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(16), default="building")
    chunker_version: Mapped[str] = mapped_column(String(64))
    chunk_size: Mapped[int] = mapped_column(Integer())
    chunk_overlap: Mapped[int] = mapped_column(Integer())
    pipeline_config_hash: Mapped[str] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeDocumentActiveGeneration(Base):
    __tablename__ = "knowledge_document_active_generations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
            name="fk_active_generations_workspace_document",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "document_id", "generation_id"],
            [
                "knowledge_generations.workspace_id",
                "knowledge_generations.document_id",
                "knowledge_generations.id",
            ],
            name="fk_active_generations_workspace_generation",
        ),
        UniqueConstraint("generation_id", name="uq_active_generations_generation"),
    )

    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    document_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    generation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_knowledge_chunks_workspace_id_id"),
        UniqueConstraint("generation_id", "position", name="uq_chunks_generation_position"),
        ForeignKeyConstraint(
            ["workspace_id", "generation_id"],
            ["knowledge_generations.workspace_id", "knowledge_generations.id"],
            name="fk_chunks_workspace_generation",
        ),
        CheckConstraint("position >= 0", name="ck_chunks_position"),
        CheckConstraint("length(content) > 0", name="ck_chunks_content_nonempty"),
        Index("ix_chunks_workspace_generation", "workspace_id", "generation_id", "position"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    generation_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    position: Mapped[int] = mapped_column(Integer())
    content: Mapped[str] = mapped_column(Text())
    content_sha256: Mapped[str] = mapped_column(String(64))
    source_locator: Mapped[str] = mapped_column(String(500))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeChunkEmbedding(Base):
    __tablename__ = "knowledge_chunk_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "chunk_id"],
            ["knowledge_chunks.workspace_id", "knowledge_chunks.id"],
            name="fk_chunk_embeddings_workspace_chunk",
        ),
        UniqueConstraint(
            "workspace_id",
            "chunk_id",
            "embedding_profile_id",
            name="uq_chunk_embeddings_workspace_chunk_profile",
        ),
        UniqueConstraint(
            "embedding_profile_id", "qdrant_point_id", name="uq_chunk_embeddings_profile_point"
        ),
        CheckConstraint(
            "status IN ('queued','indexed','failed','deleting','deleted')",
            name="ck_chunk_embeddings_status",
        ),
        Index(
            "ix_chunk_embeddings_workspace_profile_status",
            "workspace_id",
            "embedding_profile_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    chunk_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    embedding_profile_id: Mapped[int] = mapped_column(ForeignKey("embedding_profiles.id"))
    qdrant_point_id: Mapped[UUID] = mapped_column(unique=False)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


ACTIVE_JOB_PREDICATE = (
    "status IN ('uploading','awaiting_profile','queued','processing','retry_scheduled')"
)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_ingestion_jobs_workspace_id_id"),
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_ingestion_jobs_workspace_idempotency"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
            name="fk_ingestion_jobs_workspace_document",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "document_id", "document_version_id"],
            [
                "knowledge_document_versions.workspace_id",
                "knowledge_document_versions.document_id",
                "knowledge_document_versions.id",
            ],
            name="fk_ingestion_jobs_workspace_version",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "document_id", "target_generation_id"],
            [
                "knowledge_generations.workspace_id",
                "knowledge_generations.document_id",
                "knowledge_generations.id",
            ],
            name="fk_ingestion_jobs_workspace_generation",
        ),
        CheckConstraint(
            "status IN ('uploading','awaiting_profile','queued','processing','retry_scheduled',"
            "'succeeded','failed','cancelled')",
            name="ck_ingestion_jobs_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_ingestion_jobs_attempts"),
        CheckConstraint("lease_version >= 0", name="ck_ingestion_jobs_lease_version"),
        Index(
            "uq_ingestion_jobs_active_document",
            "document_id",
            unique=True,
            postgresql_where=text(ACTIVE_JOB_PREDICATE),
            sqlite_where=text(ACTIVE_JOB_PREDICATE),
        ),
        Index(
            "ix_ingestion_jobs_claim",
            "status",
            "scheduled_at",
            "lease_expires_at",
            "id",
        ),
        Index("ix_ingestion_jobs_workspace_created", "workspace_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    document_version_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    target_generation_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="awaiting_profile")
    attempts: Mapped[int] = mapped_column(Integer(), default=0)
    lease_version: Mapped[int] = mapped_column(Integer(), default=0)
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_sha256: Mapped[str] = mapped_column(String(64))
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestionJobAttempt(Base):
    __tablename__ = "ingestion_job_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["ingestion_jobs.workspace_id", "ingestion_jobs.id"],
            name="fk_ingestion_attempts_workspace_job",
        ),
        UniqueConstraint("job_id", "attempt_no", name="uq_ingestion_attempts_number"),
        CheckConstraint(
            "status IN ('processing','succeeded','failed','cancelled','lease_lost')",
            name="ck_ingestion_attempts_status",
        ),
        Index("ix_ingestion_attempts_workspace_job", "workspace_id", "job_id", "attempt_no"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    job_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    attempt_no: Mapped[int] = mapped_column(Integer())
    lease_version: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(16), default="processing")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeRecoveryEvent(Base):
    __tablename__ = "knowledge_recovery_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["ingestion_jobs.workspace_id", "ingestion_jobs.id"],
            name="fk_knowledge_recovery_events_workspace_job",
        ),
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_knowledge_recovery_events_workspace_idempotency",
        ),
        CheckConstraint(
            "action IN ('retry','rebuild')", name="ck_knowledge_recovery_events_action"
        ),
        CheckConstraint(
            "length(trim(reason)) > 0", name="ck_knowledge_recovery_events_reason_nonempty"
        ),
        Index(
            "ix_knowledge_recovery_events_workspace_job_created",
            "workspace_id",
            "job_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    job_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
