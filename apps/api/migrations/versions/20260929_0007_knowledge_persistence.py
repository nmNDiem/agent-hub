"""Add versioned knowledge persistence and durable ingestion jobs.

Revision ID: 20260929_0007
Revises: 20260927_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0007"
down_revision: str | None = "20260927_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
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
        "embedding_profiles",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("provider_model_revision", sa.String(200), nullable=True),
        sa.Column("pipeline_version", sa.String(64), nullable=False),
        sa.Column("distance_metric", sa.String(16), nullable=False),
        sa.Column("qdrant_collection", sa.String(200), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="building", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("dimensions > 0", name="ck_embedding_profiles_dimensions"),
        sa.CheckConstraint(
            "distance_metric IN ('cosine','dot','euclid')",
            name="ck_embedding_profiles_distance_metric",
        ),
        sa.CheckConstraint(
            "status IN ('building','active','deprecated','failed')",
            name="ck_embedding_profiles_status",
        ),
        sa.UniqueConstraint("qdrant_collection", name="uq_embedding_profiles_qdrant_collection"),
        sa.UniqueConstraint("config_hash", name="uq_embedding_profiles_config_hash"),
    )

    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(24), server_default="general", nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column(
            "active_embedding_profile_id",
            sa.BigInteger(),
            sa.ForeignKey("embedding_profiles.id"),
            nullable=True,
        ),
        sa.Column(
            "target_embedding_profile_id",
            sa.BigInteger(),
            sa.ForeignKey("embedding_profiles.id"),
            nullable=True,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_knowledge_bases_name_nonempty"),
        sa.CheckConstraint(
            "kind IN ('shop','faq','policy','general')", name="ck_knowledge_bases_kind"
        ),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_knowledge_bases_status"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_knowledge_bases_workspace_id_id"),
    )
    op.create_index("ix_knowledge_bases_workspace_id", "knowledge_bases", ["workspace_id"])
    op.create_index(
        "ix_knowledge_bases_workspace_status_created",
        "knowledge_bases",
        ["workspace_id", "status", "created_at", "id"],
    )

    op.create_table(
        "agent_knowledge_bases",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("agent_id", sa.BigInteger(), primary_key=True),
        sa.Column("knowledge_base_id", sa.BigInteger(), primary_key=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "agent_id"],
            ["agents.workspace_id", "agents.id"],
            name="fk_agent_knowledge_bases_workspace_agent",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "knowledge_base_id"],
            ["knowledge_bases.workspace_id", "knowledge_bases.id"],
            name="fk_agent_knowledge_bases_workspace_base",
        ),
    )
    op.create_index(
        "ix_agent_knowledge_bases_workspace_base",
        "agent_knowledge_bases",
        ["workspace_id", "knowledge_base_id"],
    )

    op.create_table(
        "media_assets",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("bucket", sa.String(120), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("visibility", sa.String(16), server_default="private", nullable=False),
        sa.Column("status", sa.String(24), server_default="reserved", nullable=False),
        sa.Column("cleanup_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deletion_due_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint("byte_size >= 0", name="ck_media_assets_byte_size"),
        sa.CheckConstraint("visibility = 'private'", name="ck_media_assets_private"),
        sa.CheckConstraint(
            "status IN ('reserved','available','delete_pending','deleted','failed')",
            name="ck_media_assets_status",
        ),
        sa.UniqueConstraint("object_key", name="uq_media_assets_object_key"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_media_assets_workspace_id_id"),
    )
    op.create_index("ix_media_assets_workspace_id", "media_assets", ["workspace_id"])
    op.create_index(
        "ix_media_assets_workspace_status", "media_assets", ["workspace_id", "status", "id"]
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("knowledge_base_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_due_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id", "knowledge_base_id"],
            ["knowledge_bases.workspace_id", "knowledge_bases.id"],
            name="fk_knowledge_documents_workspace_base",
        ),
        sa.CheckConstraint(
            "kind IN ('profile','faq','policy','size_guidance','document')",
            name="ck_knowledge_documents_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active','deleted')", name="ck_knowledge_documents_status"
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_knowledge_documents_workspace_id_id"),
    )
    op.create_index("ix_knowledge_documents_workspace_id", "knowledge_documents", ["workspace_id"])
    op.create_index(
        "ix_knowledge_documents_workspace_base_status",
        "knowledge_documents",
        ["workspace_id", "knowledge_base_id", "status", "id"],
    )

    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("media_asset_id", sa.BigInteger(), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
            name="fk_document_versions_workspace_document",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "media_asset_id"],
            ["media_assets.workspace_id", "media_assets.id"],
            name="fk_document_versions_workspace_asset",
        ),
        sa.CheckConstraint("version_no > 0", name="ck_document_versions_number"),
        sa.CheckConstraint(
            "source_kind IN ('manual','file')", name="ck_document_versions_source_kind"
        ),
        sa.CheckConstraint(
            "(source_kind = 'manual' AND source_text IS NOT NULL AND media_asset_id IS NULL) OR "
            "(source_kind = 'file' AND source_text IS NULL AND media_asset_id IS NOT NULL)",
            name="ck_document_versions_source",
        ),
        sa.UniqueConstraint(
            "workspace_id", "id", name="uq_knowledge_document_versions_workspace_id_id"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "document_id",
            "id",
            name="uq_document_versions_workspace_document_id",
        ),
        sa.UniqueConstraint("document_id", "version_no", name="uq_document_versions_number"),
    )
    op.create_index(
        "ix_document_versions_workspace_document",
        "knowledge_document_versions",
        ["workspace_id", "document_id", "version_no"],
    )
    op.create_index(
        "ix_knowledge_document_versions_workspace_id",
        "knowledge_document_versions",
        ["workspace_id"],
    )

    op.create_table(
        "knowledge_generations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("document_version_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "embedding_profile_id",
            sa.BigInteger(),
            sa.ForeignKey("embedding_profiles.id"),
            nullable=False,
        ),
        sa.Column("generation_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="building", nullable=False),
        sa.Column("chunker_version", sa.String(64), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("pipeline_config_hash", sa.String(64), nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
            name="fk_generations_workspace_document",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id", "document_version_id"],
            [
                "knowledge_document_versions.workspace_id",
                "knowledge_document_versions.document_id",
                "knowledge_document_versions.id",
            ],
            name="fk_generations_workspace_version",
        ),
        sa.CheckConstraint("generation_no > 0", name="ck_generations_number"),
        sa.CheckConstraint(
            "status IN ('building','ready','failed','revoked')", name="ck_generations_status"
        ),
        sa.CheckConstraint("chunk_size > 0", name="ck_generations_chunk_size"),
        sa.CheckConstraint(
            "chunk_overlap >= 0 AND chunk_overlap < chunk_size",
            name="ck_generations_chunk_overlap",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_knowledge_generations_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "document_id",
            "id",
            name="uq_generations_workspace_document_id",
        ),
        sa.UniqueConstraint("document_id", "generation_no", name="uq_generations_document_number"),
    )
    op.create_index(
        "ix_knowledge_generations_workspace_id",
        "knowledge_generations",
        ["workspace_id"],
    )
    op.create_index(
        "ix_generations_workspace_document_status",
        "knowledge_generations",
        ["workspace_id", "document_id", "status", "generation_no"],
    )

    op.create_table(
        "knowledge_document_active_generations",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("document_id", sa.BigInteger(), primary_key=True),
        sa.Column("generation_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "activated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
            name="fk_active_generations_workspace_document",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id", "generation_id"],
            [
                "knowledge_generations.workspace_id",
                "knowledge_generations.document_id",
                "knowledge_generations.id",
            ],
            name="fk_active_generations_workspace_generation",
        ),
        sa.UniqueConstraint("generation_id", name="uq_active_generations_generation"),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("generation_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("source_locator", sa.String(500), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "generation_id"],
            ["knowledge_generations.workspace_id", "knowledge_generations.id"],
            name="fk_chunks_workspace_generation",
        ),
        sa.CheckConstraint("position >= 0", name="ck_chunks_position"),
        sa.CheckConstraint("length(content) > 0", name="ck_chunks_content_nonempty"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_knowledge_chunks_workspace_id_id"),
        sa.UniqueConstraint("generation_id", "position", name="uq_chunks_generation_position"),
    )
    op.create_index("ix_knowledge_chunks_workspace_id", "knowledge_chunks", ["workspace_id"])
    op.create_index(
        "ix_chunks_workspace_generation",
        "knowledge_chunks",
        ["workspace_id", "generation_id", "position"],
    )

    op.create_table(
        "knowledge_chunk_embeddings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "embedding_profile_id",
            sa.BigInteger(),
            sa.ForeignKey("embedding_profiles.id"),
            nullable=False,
        ),
        sa.Column("qdrant_point_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "chunk_id"],
            ["knowledge_chunks.workspace_id", "knowledge_chunks.id"],
            name="fk_chunk_embeddings_workspace_chunk",
        ),
        sa.CheckConstraint(
            "status IN ('queued','indexed','failed','deleting','deleted')",
            name="ck_chunk_embeddings_status",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "chunk_id",
            "embedding_profile_id",
            name="uq_chunk_embeddings_workspace_chunk_profile",
        ),
        sa.UniqueConstraint(
            "embedding_profile_id", "qdrant_point_id", name="uq_chunk_embeddings_profile_point"
        ),
    )
    op.create_index(
        "ix_knowledge_chunk_embeddings_workspace_id",
        "knowledge_chunk_embeddings",
        ["workspace_id"],
    )
    op.create_index(
        "ix_chunk_embeddings_workspace_profile_status",
        "knowledge_chunk_embeddings",
        ["workspace_id", "embedding_profile_id", "status"],
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("document_version_id", sa.BigInteger(), nullable=False),
        sa.Column("target_generation_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(24), server_default="awaiting_profile", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scheduled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("retryable", sa.Boolean(), server_default=sa.false(), nullable=False),
        *timestamps(),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id"],
            ["knowledge_documents.workspace_id", "knowledge_documents.id"],
            name="fk_ingestion_jobs_workspace_document",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id", "document_version_id"],
            [
                "knowledge_document_versions.workspace_id",
                "knowledge_document_versions.document_id",
                "knowledge_document_versions.id",
            ],
            name="fk_ingestion_jobs_workspace_version",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "document_id", "target_generation_id"],
            [
                "knowledge_generations.workspace_id",
                "knowledge_generations.document_id",
                "knowledge_generations.id",
            ],
            name="fk_ingestion_jobs_workspace_generation",
        ),
        sa.CheckConstraint(
            "status IN ('uploading','awaiting_profile','queued','processing','retry_scheduled',"
            "'succeeded','failed','cancelled')",
            name="ck_ingestion_jobs_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_ingestion_jobs_attempts"),
        sa.CheckConstraint("lease_version >= 0", name="ck_ingestion_jobs_lease_version"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_ingestion_jobs_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_ingestion_jobs_workspace_idempotency"
        ),
    )
    op.create_index("ix_ingestion_jobs_workspace_id", "ingestion_jobs", ["workspace_id"])
    op.create_index(
        "uq_ingestion_jobs_active_document",
        "ingestion_jobs",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('uploading','awaiting_profile','queued','processing','retry_scheduled')"
        ),
    )
    op.create_index(
        "ix_ingestion_jobs_claim",
        "ingestion_jobs",
        ["status", "scheduled_at", "lease_expires_at", "id"],
    )
    op.create_index(
        "ix_ingestion_jobs_workspace_created",
        "ingestion_jobs",
        ["workspace_id", "created_at", "id"],
    )

    op.create_table(
        "ingestion_job_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("lease_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="processing", nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "job_id"],
            ["ingestion_jobs.workspace_id", "ingestion_jobs.id"],
            name="fk_ingestion_attempts_workspace_job",
        ),
        sa.CheckConstraint(
            "status IN ('processing','succeeded','failed','cancelled','lease_lost')",
            name="ck_ingestion_attempts_status",
        ),
        sa.UniqueConstraint("job_id", "attempt_no", name="uq_ingestion_attempts_number"),
    )
    op.create_index(
        "ix_ingestion_attempts_workspace_job",
        "ingestion_job_attempts",
        ["workspace_id", "job_id", "attempt_no"],
    )
    op.create_index(
        "ix_ingestion_job_attempts_workspace_id", "ingestion_job_attempts", ["workspace_id"]
    )

    op.execute(
        """
        CREATE FUNCTION prevent_embedding_profile_config_update() RETURNS trigger AS $$
        BEGIN
          IF NEW.provider IS DISTINCT FROM OLD.provider
             OR NEW.model IS DISTINCT FROM OLD.model
             OR NEW.dimensions IS DISTINCT FROM OLD.dimensions
             OR NEW.provider_model_revision IS DISTINCT FROM OLD.provider_model_revision
             OR NEW.pipeline_version IS DISTINCT FROM OLD.pipeline_version
             OR NEW.distance_metric IS DISTINCT FROM OLD.distance_metric
             OR NEW.qdrant_collection IS DISTINCT FROM OLD.qdrant_collection
             OR NEW.config_hash IS DISTINCT FROM OLD.config_hash THEN
            RAISE EXCEPTION 'embedding profile configuration is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_embedding_profiles_immutable
        BEFORE UPDATE ON embedding_profiles
        FOR EACH ROW EXECUTE FUNCTION prevent_embedding_profile_config_update()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_embedding_profiles_immutable ON embedding_profiles")
    op.execute("DROP FUNCTION IF EXISTS prevent_embedding_profile_config_update()")
    op.drop_table("ingestion_job_attempts")
    op.drop_table("ingestion_jobs")
    op.drop_table("knowledge_chunk_embeddings")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_document_active_generations")
    op.drop_table("knowledge_generations")
    op.drop_table("knowledge_document_versions")
    op.drop_table("knowledge_documents")
    op.drop_table("media_assets")
    op.drop_table("agent_knowledge_bases")
    op.drop_table("knowledge_bases")
    op.drop_table("embedding_profiles")
