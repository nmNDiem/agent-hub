from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.core.config import Settings
from agent_hub_api.knowledge.ingestion import profile_spec
from agent_hub_api.knowledge.models import (
    EmbeddingProfile,
    IngestionJob,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeDocumentActiveGeneration,
    KnowledgeDocumentVersion,
    KnowledgeGeneration,
)
from agent_hub_api.knowledge.pipeline import create_generation
from agent_hub_api.knowledge.providers import KnowledgeVectorIndex


@dataclass(frozen=True, slots=True)
class EmbeddingProfileConfiguration:
    provider: str
    model: str
    dimensions: int
    provider_model_revision: str | None
    pipeline_version: str
    distance_metric: str
    collection: str

    @property
    def config_hash(self) -> str:
        serialized = json.dumps(
            {
                "provider": self.provider,
                "model": self.model,
                "dimensions": self.dimensions,
                "provider_model_revision": self.provider_model_revision,
                "pipeline_version": self.pipeline_version,
                "distance_metric": self.distance_metric,
                "collection": self.collection,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode()).hexdigest()


def _job_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class KnowledgeProfileService:
    """Operator-only profile bootstrap, rebuild, backfill and atomic cutover."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        vector_index: KnowledgeVectorIndex,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.vector_index = vector_index

    async def bootstrap(self, config: EmbeddingProfileConfiguration) -> EmbeddingProfile:
        if config.provider != "openai":
            raise ValueError("F3.3 only permits the OpenAI embedding provider")
        if config.dimensions < 1 or config.distance_metric not in {"cosine", "dot", "euclid"}:
            raise ValueError("Invalid embedding profile configuration")
        async with self.session_factory() as session, session.begin():
            profile = await session.scalar(
                select(EmbeddingProfile).where(
                    EmbeddingProfile.config_hash == config.config_hash
                )
            )
            if profile is None:
                profile = EmbeddingProfile(
                    provider=config.provider,
                    model=config.model,
                    dimensions=config.dimensions,
                    provider_model_revision=config.provider_model_revision,
                    pipeline_version=config.pipeline_version,
                    distance_metric=config.distance_metric,
                    qdrant_collection=config.collection,
                    config_hash=config.config_hash,
                    status="building",
                )
                session.add(profile)
                await session.flush()
            profile_id = profile.id

        try:
            await self.vector_index.ensure_profile(profile_spec(profile))
        except Exception:
            async with self.session_factory() as session, session.begin():
                stored = await session.get(EmbeddingProfile, profile_id)
                if stored is not None and stored.status != "active":
                    stored.status = "failed"
            raise

        async with self.session_factory() as session, session.begin():
            stored = await session.get(EmbeddingProfile, profile_id)
            if stored is None:
                raise RuntimeError("Embedding profile disappeared during bootstrap")
            stored.status = "active"
            await session.flush()
            return stored

    async def activate_unprofiled_bases(
        self, *, profile_id: int, workspace_id: UUID | None = None
    ) -> int:
        queued = 0
        async with self.session_factory() as session, session.begin():
            await self._active_profile(session, profile_id)
            base_query = select(KnowledgeBase).where(
                KnowledgeBase.status == "active",
                KnowledgeBase.active_embedding_profile_id.is_(None),
            )
            if workspace_id is not None:
                base_query = base_query.where(KnowledgeBase.workspace_id == workspace_id)
            bases = list(await session.scalars(base_query.with_for_update()))
            for base in bases:
                base.active_embedding_profile_id = profile_id
                jobs = list(
                    await session.scalars(
                        select(IngestionJob)
                        .join(
                            KnowledgeDocument,
                            and_(
                                KnowledgeDocument.workspace_id == IngestionJob.workspace_id,
                                KnowledgeDocument.id == IngestionJob.document_id,
                            ),
                        )
                        .where(
                            IngestionJob.workspace_id == base.workspace_id,
                            IngestionJob.status == "awaiting_profile",
                            IngestionJob.target_generation_id.is_(None),
                            KnowledgeDocument.knowledge_base_id == base.id,
                            KnowledgeDocument.status == "active",
                        )
                        .with_for_update()
                    )
                )
                for job in jobs:
                    document = await session.scalar(
                        select(KnowledgeDocument).where(
                            KnowledgeDocument.workspace_id == base.workspace_id,
                            KnowledgeDocument.id == job.document_id,
                        )
                    )
                    version = await session.scalar(
                        select(KnowledgeDocumentVersion).where(
                            KnowledgeDocumentVersion.workspace_id == base.workspace_id,
                            KnowledgeDocumentVersion.id == job.document_version_id,
                            KnowledgeDocumentVersion.document_id == job.document_id,
                        )
                    )
                    if document is None or version is None:
                        raise RuntimeError("Awaiting job references missing source rows")
                    generation = await create_generation(
                        session,
                        document=document,
                        version=version,
                        embedding_profile_id=profile_id,
                        settings=self.settings,
                    )
                    job.target_generation_id = generation.id
                    job.status = "queued"
                    job.scheduled_at = datetime.now(UTC)
                    job.updated_at = datetime.now(UTC)
                    queued += 1
        return queued

    async def start_migration(
        self,
        *,
        workspace_id: UUID,
        knowledge_base_id: int,
        target_profile_id: int,
        operation_id: str,
    ) -> int:
        queued = 0
        async with self.session_factory() as session, session.begin():
            await self._active_profile(session, target_profile_id)
            base = await session.scalar(
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.workspace_id == workspace_id,
                    KnowledgeBase.id == knowledge_base_id,
                    KnowledgeBase.status == "active",
                )
                .with_for_update()
            )
            if base is None:
                raise LookupError("Knowledge base not found")
            if base.active_embedding_profile_id is None:
                raise ValueError("Use initial profile activation for an unprofiled base")
            if base.active_embedding_profile_id == target_profile_id:
                return 0
            if base.target_embedding_profile_id not in {None, target_profile_id}:
                raise RuntimeError("Knowledge base already has another target profile")
            base.target_embedding_profile_id = target_profile_id
            documents = list(
                await session.scalars(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.workspace_id == workspace_id,
                        KnowledgeDocument.knowledge_base_id == knowledge_base_id,
                        KnowledgeDocument.status == "active",
                    )
                )
            )
            for document in documents:
                key = f"profile:{operation_id}:{target_profile_id}:{document.id}"
                existing = await session.scalar(
                    select(IngestionJob.id).where(
                        IngestionJob.workspace_id == workspace_id,
                        IngestionJob.idempotency_key == key,
                    )
                )
                if existing is not None:
                    continue
                await self._assert_no_active_job(session, workspace_id, document.id)
                version = await self._latest_version(session, workspace_id, document.id)
                generation = await create_generation(
                    session,
                    document=document,
                    version=version,
                    embedding_profile_id=target_profile_id,
                    settings=self.settings,
                )
                session.add(
                    IngestionJob(
                        workspace_id=workspace_id,
                        document_id=document.id,
                        document_version_id=version.id,
                        target_generation_id=generation.id,
                        status="queued",
                        idempotency_key=key,
                        request_sha256=_job_hash(key),
                    )
                )
                queued += 1
        return queued

    async def queue_rebuild(
        self,
        *,
        profile_id: int,
        operation_id: str,
        workspace_id: UUID | None = None,
    ) -> int:
        queued = 0
        async with self.session_factory() as session, session.begin():
            await self._active_profile(session, profile_id)
            query = (
                select(
                    KnowledgeDocument,
                    KnowledgeDocumentVersion,
                    KnowledgeDocumentActiveGeneration,
                )
                .join(
                    KnowledgeBase,
                    and_(
                        KnowledgeBase.workspace_id == KnowledgeDocument.workspace_id,
                        KnowledgeBase.id == KnowledgeDocument.knowledge_base_id,
                    ),
                )
                .join(
                    KnowledgeDocumentActiveGeneration,
                    and_(
                        KnowledgeDocumentActiveGeneration.workspace_id
                        == KnowledgeDocument.workspace_id,
                        KnowledgeDocumentActiveGeneration.document_id == KnowledgeDocument.id,
                    ),
                )
                .join(
                    KnowledgeGeneration,
                    and_(
                        KnowledgeGeneration.workspace_id == KnowledgeDocument.workspace_id,
                        KnowledgeGeneration.id
                        == KnowledgeDocumentActiveGeneration.generation_id,
                    ),
                )
                .join(
                    KnowledgeDocumentVersion,
                    and_(
                        KnowledgeDocumentVersion.workspace_id
                        == KnowledgeDocument.workspace_id,
                        KnowledgeDocumentVersion.id
                        == KnowledgeGeneration.document_version_id,
                    ),
                )
                .where(
                    KnowledgeDocument.status == "active",
                    KnowledgeBase.status == "active",
                    KnowledgeBase.active_embedding_profile_id == profile_id,
                    KnowledgeGeneration.status == "ready",
                    KnowledgeGeneration.embedding_profile_id == profile_id,
                )
            )
            if workspace_id is not None:
                query = query.where(KnowledgeDocument.workspace_id == workspace_id)
            for document, version, active in (await session.execute(query)).all():
                key = f"rebuild:{operation_id}:{profile_id}:{document.id}"
                existing = await session.scalar(
                    select(IngestionJob.id).where(
                        IngestionJob.workspace_id == document.workspace_id,
                        IngestionJob.idempotency_key == key,
                    )
                )
                if existing is not None:
                    continue
                await self._assert_no_active_job(
                    session, document.workspace_id, document.id
                )
                session.add(
                    IngestionJob(
                        workspace_id=document.workspace_id,
                        document_id=document.id,
                        document_version_id=version.id,
                        target_generation_id=active.generation_id,
                        status="queued",
                        idempotency_key=key,
                        request_sha256=_job_hash(key),
                    )
                )
                queued += 1
        return queued

    async def promote(
        self, *, workspace_id: UUID, knowledge_base_id: int
    ) -> int:
        async with self.session_factory() as session, session.begin():
            base = await session.scalar(
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.workspace_id == workspace_id,
                    KnowledgeBase.id == knowledge_base_id,
                    KnowledgeBase.status == "active",
                )
                .with_for_update()
            )
            if base is None:
                raise LookupError("Knowledge base not found")
            target_profile_id = base.target_embedding_profile_id
            if target_profile_id is None:
                raise ValueError("Knowledge base does not have a target profile")
            documents = list(
                await session.scalars(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.workspace_id == workspace_id,
                        KnowledgeDocument.knowledge_base_id == knowledge_base_id,
                        KnowledgeDocument.status == "active",
                    )
                )
            )
            generations: dict[int, KnowledgeGeneration] = {}
            for document in documents:
                generation = await session.scalar(
                    select(KnowledgeGeneration)
                    .where(
                        KnowledgeGeneration.workspace_id == workspace_id,
                        KnowledgeGeneration.document_id == document.id,
                        KnowledgeGeneration.embedding_profile_id == target_profile_id,
                        KnowledgeGeneration.status == "ready",
                    )
                    .order_by(KnowledgeGeneration.generation_no.desc())
                    .limit(1)
                )
                if generation is None or not await self._generation_is_fully_indexed(
                    session, workspace_id, generation.id
                ):
                    raise RuntimeError("Target profile backfill is incomplete")
                generations[document.id] = generation

            now = datetime.now(UTC)
            for document_id, generation in generations.items():
                active = await session.scalar(
                    select(KnowledgeDocumentActiveGeneration)
                    .where(
                        KnowledgeDocumentActiveGeneration.workspace_id == workspace_id,
                        KnowledgeDocumentActiveGeneration.document_id == document_id,
                    )
                    .with_for_update()
                )
                if active is None:
                    session.add(
                        KnowledgeDocumentActiveGeneration(
                            workspace_id=workspace_id,
                            document_id=document_id,
                            generation_id=generation.id,
                            activated_at=now,
                        )
                    )
                else:
                    active.generation_id = generation.id
                    active.activated_at = now
            base.active_embedding_profile_id = target_profile_id
            base.target_embedding_profile_id = None
            base.updated_at = now
            return len(generations)

    @staticmethod
    async def _active_profile(session: AsyncSession, profile_id: int) -> EmbeddingProfile:
        profile = await session.scalar(
            select(EmbeddingProfile).where(
                EmbeddingProfile.id == profile_id,
                EmbeddingProfile.status == "active",
            )
        )
        if profile is None:
            raise LookupError("Active embedding profile not found")
        return profile

    @staticmethod
    async def _assert_no_active_job(
        session: AsyncSession, workspace_id: UUID, document_id: int
    ) -> None:
        active = await session.scalar(
            select(IngestionJob.id).where(
                IngestionJob.workspace_id == workspace_id,
                IngestionJob.document_id == document_id,
                IngestionJob.status.in_(
                    {"uploading", "awaiting_profile", "queued", "processing", "retry_scheduled"}
                ),
            )
        )
        if active is not None:
            raise RuntimeError("Document already has an active ingestion job")

    @staticmethod
    async def _latest_version(
        session: AsyncSession, workspace_id: UUID, document_id: int
    ) -> KnowledgeDocumentVersion:
        version = await session.scalar(
            select(KnowledgeDocumentVersion)
            .where(
                KnowledgeDocumentVersion.workspace_id == workspace_id,
                KnowledgeDocumentVersion.document_id == document_id,
            )
            .order_by(KnowledgeDocumentVersion.version_no.desc())
            .limit(1)
        )
        if version is None:
            raise RuntimeError("Knowledge document has no source version")
        return version

    @staticmethod
    async def _generation_is_fully_indexed(
        session: AsyncSession, workspace_id: UUID, generation_id: int
    ) -> bool:
        total = int(
            await session.scalar(
                select(func.count(KnowledgeChunk.id)).where(
                    KnowledgeChunk.workspace_id == workspace_id,
                    KnowledgeChunk.generation_id == generation_id,
                )
            )
            or 0
        )
        indexed = int(
            await session.scalar(
                select(func.count(KnowledgeChunkEmbedding.id))
                .join(
                    KnowledgeChunk,
                    and_(
                        KnowledgeChunk.workspace_id == KnowledgeChunkEmbedding.workspace_id,
                        KnowledgeChunk.id == KnowledgeChunkEmbedding.chunk_id,
                    ),
                )
                .join(
                    KnowledgeGeneration,
                    and_(
                        KnowledgeGeneration.workspace_id == KnowledgeChunk.workspace_id,
                        KnowledgeGeneration.id == KnowledgeChunk.generation_id,
                    ),
                )
                .where(
                    KnowledgeChunk.workspace_id == workspace_id,
                    KnowledgeChunk.generation_id == generation_id,
                    KnowledgeChunkEmbedding.status == "indexed",
                    KnowledgeChunkEmbedding.embedding_profile_id
                    == KnowledgeGeneration.embedding_profile_id,
                )
            )
            or 0
        )
        return total > 0 and indexed == total
