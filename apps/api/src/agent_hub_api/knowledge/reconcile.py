from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.core.config import Settings
from agent_hub_api.knowledge.ingestion import profile_spec
from agent_hub_api.knowledge.models import (
    EmbeddingProfile,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeGeneration,
    MediaAsset,
)
from agent_hub_api.knowledge.providers import KnowledgeVectorIndex, ProviderTemporaryError
from agent_hub_api.knowledge.storage import KnowledgeStorage

logger = logging.getLogger(__name__)


class KnowledgeReconciler:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        storage: KnowledgeStorage,
        vector_index: KnowledgeVectorIndex,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.storage = storage
        self.vector_index = vector_index

    async def mark_stale_vectors(self) -> int:
        async with self.session_factory() as session, session.begin():
            result = await session.execute(
                update(KnowledgeChunkEmbedding)
                .where(
                    KnowledgeChunkEmbedding.status.in_({"queued", "indexed", "failed"}),
                    KnowledgeChunkEmbedding.chunk_id.in_(
                        select(KnowledgeChunk.id)
                        .join(
                            KnowledgeGeneration,
                            and_(
                                KnowledgeGeneration.workspace_id == KnowledgeChunk.workspace_id,
                                KnowledgeGeneration.id == KnowledgeChunk.generation_id,
                            ),
                        )
                        .where(KnowledgeGeneration.status.in_({"failed", "revoked"}))
                    ),
                )
                .values(status="deleting")
            )
            return int(getattr(result, "rowcount", 0))

    async def reconcile_vectors_once(self) -> bool:
        async with self.session_factory() as session:
            first = await session.scalar(
                select(KnowledgeChunkEmbedding)
                .where(KnowledgeChunkEmbedding.status == "deleting")
                .order_by(KnowledgeChunkEmbedding.id)
                .limit(1)
            )
            if first is None:
                return False
            mappings = list(
                (
                    await session.scalars(
                        select(KnowledgeChunkEmbedding)
                        .where(
                            KnowledgeChunkEmbedding.status == "deleting",
                            KnowledgeChunkEmbedding.embedding_profile_id
                            == first.embedding_profile_id,
                        )
                        .order_by(KnowledgeChunkEmbedding.id)
                        .limit(self.settings.knowledge_embedding_batch_size)
                    )
                ).all()
            )
            profile = await session.get(EmbeddingProfile, first.embedding_profile_id)
            if profile is None:
                raise RuntimeError("Chunk embedding references a missing profile")
            mapping_ids = [mapping.id for mapping in mappings]
            point_ids = [mapping.qdrant_point_id for mapping in mappings]
            spec = profile_spec(profile)
        try:
            await self.vector_index.delete(spec, point_ids)
        except ProviderTemporaryError:
            logger.warning(
                "knowledge_vector_cleanup_deferred profile_id=%s count=%s",
                first.embedding_profile_id,
                len(point_ids),
            )
            return False
        async with self.session_factory() as session, session.begin():
            await session.execute(
                update(KnowledgeChunkEmbedding)
                .where(
                    KnowledgeChunkEmbedding.id.in_(mapping_ids),
                    KnowledgeChunkEmbedding.status == "deleting",
                )
                .values(status="deleted", error_code=None)
            )
        return True

    async def reconcile_storage_once(self) -> bool:
        cutoff = datetime.now(UTC) - timedelta(
            seconds=self.settings.knowledge_orphan_grace_seconds
        )
        async with self.session_factory() as session:
            asset = await session.scalar(
                select(MediaAsset)
                .where(
                    (MediaAsset.status == "delete_pending")
                    | (
                        MediaAsset.status.in_({"reserved", "failed"})
                        & (MediaAsset.updated_at <= cutoff)
                    )
                )
                .order_by(MediaAsset.id)
                .limit(1)
            )
            if asset is None:
                return False
            asset_id = asset.id
            object_key = asset.object_key
        await self.storage.delete(object_key=object_key)
        async with self.session_factory() as session, session.begin():
            await session.execute(
                update(MediaAsset)
                .where(
                    MediaAsset.id == asset_id,
                    MediaAsset.status.in_({"delete_pending", "reserved", "failed"}),
                )
                .values(status="deleted", updated_at=datetime.now(UTC))
            )
        return True

    async def run_once(self) -> bool:
        await self.mark_stale_vectors()
        vector_work = await self.reconcile_vectors_once()
        storage_work = await self.reconcile_storage_once()
        if vector_work or storage_work:
            logger.info(
                "knowledge_reconcile_completed vector=%s storage=%s",
                vector_work,
                storage_work,
            )
        return vector_work or storage_work
