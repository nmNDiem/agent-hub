from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4, uuid5

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.core.config import Settings
from agent_hub_api.knowledge.chunking import TextChunk, chunk_text
from agent_hub_api.knowledge.extraction import (
    ExtractionError,
    ExtractionLimits,
    extract_pdf,
    extract_text_file,
    normalize_document_text,
)
from agent_hub_api.knowledge.models import (
    EmbeddingProfile,
    IngestionJob,
    IngestionJobAttempt,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeDocumentActiveGeneration,
    KnowledgeDocumentVersion,
    KnowledgeGeneration,
    MediaAsset,
)
from agent_hub_api.knowledge.providers import (
    EmbeddingProfileSpec,
    EmbeddingProvider,
    KnowledgeVectorIndex,
    ProviderPermanentError,
    ProviderTemporaryError,
    VectorPoint,
)
from agent_hub_api.knowledge.storage import KnowledgeStorage, KnowledgeStorageError
from agent_hub_api.workspaces.models import Workspace

logger = logging.getLogger(__name__)
POINT_NAMESPACE = UUID("5c0a7e71-0b09-5dc0-9f94-0a6f7a71772f")


class LeaseLost(RuntimeError):
    pass


class IngestionFailure(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    job_id: int
    workspace_id: UUID
    lease_token: UUID
    lease_version: int
    attempt_no: int


@dataclass(frozen=True, slots=True)
class IngestionContext:
    job: IngestionJob
    document: KnowledgeDocument
    version: KnowledgeDocumentVersion
    generation: KnowledgeGeneration
    knowledge_base: KnowledgeBase
    profile: EmbeddingProfile
    asset: MediaAsset | None


@dataclass(frozen=True, slots=True)
class ChunkWork:
    chunk_id: int
    position: int
    content: str
    content_hash: str
    point_id: UUID


def profile_spec(profile: EmbeddingProfile) -> EmbeddingProfileSpec:
    return EmbeddingProfileSpec(
        id=profile.id,
        provider=profile.provider,
        model=profile.model,
        dimensions=profile.dimensions,
        provider_model_revision=profile.provider_model_revision,
        pipeline_version=profile.pipeline_version,
        distance_metric=profile.distance_metric,
        collection=profile.qdrant_collection,
        config_hash=profile.config_hash,
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class KnowledgeIngestionWorker:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        storage: KnowledgeStorage,
        embedding_provider: EmbeddingProvider,
        vector_index: KnowledgeVectorIndex,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.storage = storage
        self.embedding_provider = embedding_provider
        self.vector_index = vector_index

    async def claim_next(self) -> ClaimedJob | None:
        now = datetime.now(UTC)
        eligible = or_(
            and_(
                IngestionJob.status.in_({"queued", "retry_scheduled"}),
                IngestionJob.scheduled_at <= now,
            ),
            and_(
                IngestionJob.status == "processing",
                IngestionJob.lease_expires_at < now,
            ),
        )
        async with self.session_factory() as session, session.begin():
            candidates = list(
                (
                    await session.scalars(
                        select(IngestionJob)
                        .where(eligible)
                        .order_by(IngestionJob.scheduled_at, IngestionJob.id)
                        .limit(20)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            for job in candidates:
                await session.scalar(
                    select(Workspace)
                    .where(Workspace.id == job.workspace_id)
                    .with_for_update()
                )
                active_count = int(
                    await session.scalar(
                        select(func.count(IngestionJob.id)).where(
                            IngestionJob.workspace_id == job.workspace_id,
                            IngestionJob.status == "processing",
                            IngestionJob.lease_expires_at >= now,
                            IngestionJob.id != job.id,
                        )
                    )
                    or 0
                )
                if active_count >= self.settings.knowledge_workspace_active_jobs:
                    continue
                if job.attempts >= self.settings.knowledge_job_max_attempts:
                    job.status = "failed"
                    job.retryable = False
                    job.last_error_code = "INGESTION_ATTEMPTS_EXHAUSTED"
                    job.completed_at = now
                    continue
                if job.status == "processing":
                    await session.execute(
                        update(IngestionJobAttempt)
                        .where(
                            IngestionJobAttempt.job_id == job.id,
                            IngestionJobAttempt.status == "processing",
                        )
                        .values(status="lease_lost", finished_at=now)
                    )
                token = uuid4()
                job.status = "processing"
                job.attempts += 1
                job.lease_version += 1
                job.lease_token = token
                job.heartbeat_at = now
                job.lease_expires_at = now + timedelta(
                    seconds=self.settings.knowledge_job_lease_seconds
                )
                job.updated_at = now
                session.add(
                    IngestionJobAttempt(
                        workspace_id=job.workspace_id,
                        job_id=job.id,
                        attempt_no=job.attempts,
                        lease_version=job.lease_version,
                    )
                )
                return ClaimedJob(
                    job_id=job.id,
                    workspace_id=job.workspace_id,
                    lease_token=token,
                    lease_version=job.lease_version,
                    attempt_no=job.attempts,
                )
        return None

    async def heartbeat(self, claim: ClaimedJob) -> bool:
        now = datetime.now(UTC)
        async with self.session_factory() as session, session.begin():
            result = await session.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.id == claim.job_id,
                    IngestionJob.workspace_id == claim.workspace_id,
                    IngestionJob.status == "processing",
                    IngestionJob.lease_token == claim.lease_token,
                    IngestionJob.lease_version == claim.lease_version,
                )
                .values(
                    heartbeat_at=now,
                    lease_expires_at=now
                    + timedelta(seconds=self.settings.knowledge_job_lease_seconds),
                    updated_at=now,
                )
            )
            return bool(cast(Any, result).rowcount)

    async def _heartbeat_loop(self, claim: ClaimedJob, stop: asyncio.Event) -> None:
        while True:
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=self.settings.knowledge_job_heartbeat_seconds
                )
                return
            except TimeoutError:
                try:
                    renewed = await self.heartbeat(claim)
                except Exception:
                    logger.error(
                        "knowledge_ingestion_heartbeat_failed job_id=%s workspace_id=%s",
                        claim.job_id,
                        claim.workspace_id,
                    )
                    return
                if not renewed:
                    return

    async def run_once(self) -> bool:
        claim = await self.claim_next()
        if claim is None:
            return False
        stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(claim, stop))
        try:
            await self._process(claim)
        except LeaseLost:
            logger.warning(
                "knowledge_ingestion_lease_lost job_id=%s workspace_id=%s",
                claim.job_id,
                claim.workspace_id,
            )
        except ExtractionError as exc:
            await self._record_failure(claim, exc.code, retryable=exc.retryable)
        except IngestionFailure as exc:
            await self._record_failure(claim, exc.code, retryable=exc.retryable)
        except ProviderPermanentError:
            await self._record_failure(
                claim,
                "INGESTION_PROVIDER_CONFIGURATION_INVALID",
                retryable=False,
            )
        except (KnowledgeStorageError, ProviderTemporaryError):
            await self._record_failure(claim, "INGESTION_PROVIDER_UNAVAILABLE", retryable=True)
        except Exception:
            logger.error(
                "knowledge_ingestion_unexpected job_id=%s workspace_id=%s",
                claim.job_id,
                claim.workspace_id,
            )
            await self._record_failure(claim, "INGESTION_INTERNAL_ERROR", retryable=True)
        finally:
            stop.set()
            await heartbeat_task
        return True

    async def _context(self, claim: ClaimedJob) -> IngestionContext:
        async with self.session_factory() as session:
            job = await session.scalar(
                select(IngestionJob).where(
                    IngestionJob.id == claim.job_id,
                    IngestionJob.workspace_id == claim.workspace_id,
                    IngestionJob.status == "processing",
                    IngestionJob.lease_token == claim.lease_token,
                    IngestionJob.lease_version == claim.lease_version,
                )
            )
            if job is None:
                raise LeaseLost
            document = await session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == job.document_id,
                    KnowledgeDocument.workspace_id == claim.workspace_id,
                )
            )
            version = await session.scalar(
                select(KnowledgeDocumentVersion).where(
                    KnowledgeDocumentVersion.id == job.document_version_id,
                    KnowledgeDocumentVersion.workspace_id == claim.workspace_id,
                )
            )
            generation = await session.scalar(
                select(KnowledgeGeneration).where(
                    KnowledgeGeneration.id == job.target_generation_id,
                    KnowledgeGeneration.workspace_id == claim.workspace_id,
                )
            )
            if document is None or version is None or generation is None:
                raise IngestionFailure("INGESTION_STATE_INVALID", retryable=False)
            knowledge_base = await session.scalar(
                select(KnowledgeBase).where(
                    KnowledgeBase.id == document.knowledge_base_id,
                    KnowledgeBase.workspace_id == claim.workspace_id,
                )
            )
            profile = await session.get(EmbeddingProfile, generation.embedding_profile_id)
            asset = None
            if version.media_asset_id is not None:
                asset = await session.scalar(
                    select(MediaAsset).where(
                        MediaAsset.id == version.media_asset_id,
                        MediaAsset.workspace_id == claim.workspace_id,
                    )
                )
            if knowledge_base is None or profile is None:
                raise IngestionFailure("INGESTION_STATE_INVALID", retryable=False)
            if version.source_kind == "file" and (asset is None or asset.status != "available"):
                raise IngestionFailure("KNOWLEDGE_ASSET_NOT_AVAILABLE", retryable=True)
            return IngestionContext(
                job=job,
                document=document,
                version=version,
                generation=generation,
                knowledge_base=knowledge_base,
                profile=profile,
                asset=asset,
            )

    async def _extract(self, context: IngestionContext) -> str:
        if context.version.source_kind == "manual":
            text = normalize_document_text(context.version.source_text or "")
            if not text:
                raise ExtractionError("TEXT_CONTENT_EMPTY")
            return text
        if context.asset is None:
            raise IngestionFailure("KNOWLEDGE_ASSET_NOT_AVAILABLE", retryable=True)
        suffix = ".pdf" if context.version.mime_type == "application/pdf" else ".txt"
        with tempfile.TemporaryDirectory(prefix="agenthub-ingestion-") as temporary:
            path = Path(temporary) / f"source{suffix}"
            await self.storage.download_file(
                object_key=context.asset.object_key,
                destination=path,
                max_bytes=self.settings.knowledge_document_max_bytes,
            )
            downloaded_hash = await asyncio.to_thread(file_sha256, path)
            if downloaded_hash != context.version.content_sha256:
                raise IngestionFailure("KNOWLEDGE_ASSET_HASH_MISMATCH", retryable=False)
            if context.version.mime_type == "application/pdf":
                extracted = await extract_pdf(
                    path,
                    ExtractionLimits(
                        max_pages=self.settings.knowledge_pdf_max_pages,
                        max_chars=self.settings.knowledge_extracted_max_chars,
                        wall_seconds=self.settings.knowledge_parser_wall_seconds,
                        cpu_seconds=self.settings.knowledge_parser_cpu_seconds,
                        memory_bytes=self.settings.knowledge_parser_memory_bytes,
                        output_bytes=self.settings.knowledge_parser_output_bytes,
                    ),
                )
            else:
                extracted = await asyncio.to_thread(
                    extract_text_file,
                    path,
                    max_chars=self.settings.knowledge_extracted_max_chars,
                )
            return extracted.text

    async def _process(self, claim: ClaimedJob) -> None:
        context = await self._context(claim)
        if context.document.status != "active" or context.knowledge_base.status != "active":
            raise IngestionFailure("KNOWLEDGE_SOURCE_REVOKED", retryable=False)
        text = await self._extract(context)
        parsed_chunks = chunk_text(
            text,
            chunk_size=context.generation.chunk_size,
            overlap=context.generation.chunk_overlap,
            max_chunks=self.settings.knowledge_max_chunks_per_generation,
            source_prefix=f"document:{context.document.id}:version:{context.version.version_no}",
        )
        if not parsed_chunks:
            raise IngestionFailure("DOCUMENT_TEXT_EMPTY", retryable=False)
        chunks = await self._persist_chunks(claim, context, parsed_chunks)
        spec = profile_spec(context.profile)
        await self.vector_index.ensure_profile(spec)
        batch_size = self.settings.knowledge_embedding_batch_size
        for offset in range(0, len(chunks), batch_size):
            batch = chunks[offset : offset + batch_size]
            vectors = await self.embedding_provider.embed(spec, [chunk.content for chunk in batch])
            if len(vectors) != len(batch) or any(
                len(vector) != spec.dimensions for vector in vectors
            ):
                raise IngestionFailure("EMBEDDING_DIMENSION_MISMATCH", retryable=False)
            points = [
                VectorPoint(
                    point_id=chunk.point_id,
                    vector=vector,
                    payload={
                        "workspace_id": str(claim.workspace_id),
                        "knowledge_base_id": context.knowledge_base.id,
                        "document_id": context.document.id,
                        "document_version_id": context.version.id,
                        "generation_id": context.generation.id,
                        "generation": context.generation.generation_no,
                        "chunk_id": chunk.chunk_id,
                        "embedding_profile_id": context.profile.id,
                        "content_hash": chunk.content_hash,
                    },
                )
                for chunk, vector in zip(batch, vectors, strict=True)
            ]
            await self.vector_index.upsert(spec, points)
            await self._mark_indexed(claim, batch)
        await self._cutover(claim, context)

    async def _assert_fence(self, session: AsyncSession, claim: ClaimedJob) -> IngestionJob:
        job = await session.scalar(
            select(IngestionJob).where(
                IngestionJob.id == claim.job_id,
                IngestionJob.workspace_id == claim.workspace_id,
                IngestionJob.status == "processing",
                IngestionJob.lease_token == claim.lease_token,
                IngestionJob.lease_version == claim.lease_version,
            )
        )
        if job is None:
            raise LeaseLost
        return job

    async def _persist_chunks(
        self,
        claim: ClaimedJob,
        context: IngestionContext,
        parsed: list[TextChunk],
    ) -> list[ChunkWork]:
        async with self.session_factory() as session, session.begin():
            await self._assert_fence(session, claim)
            await session.scalar(
                select(Workspace)
                .where(Workspace.id == claim.workspace_id)
                .with_for_update()
            )
            other_chunk_count = int(
                await session.scalar(
                    select(func.count(KnowledgeChunk.id))
                    .join(
                        KnowledgeGeneration,
                        and_(
                            KnowledgeGeneration.workspace_id == KnowledgeChunk.workspace_id,
                            KnowledgeGeneration.id == KnowledgeChunk.generation_id,
                        ),
                    )
                    .where(
                        KnowledgeChunk.workspace_id == claim.workspace_id,
                        KnowledgeGeneration.document_id != context.document.id,
                        KnowledgeGeneration.status.in_({"building", "ready"}),
                    )
                )
                or 0
            )
            if other_chunk_count + len(parsed) > self.settings.knowledge_workspace_max_chunks:
                raise IngestionFailure("KNOWLEDGE_CHUNK_QUOTA", retryable=False)
            existing = list(
                (
                    await session.scalars(
                        select(KnowledgeChunk)
                        .where(
                            KnowledgeChunk.workspace_id == claim.workspace_id,
                            KnowledgeChunk.generation_id == context.generation.id,
                        )
                        .order_by(KnowledgeChunk.position)
                    )
                ).all()
            )
            if existing:
                if len(existing) != len(parsed) or any(
                    row.position != item.position or row.content_sha256 != item.content_sha256
                    for row, item in zip(existing, parsed, strict=False)
                ):
                    raise IngestionFailure("GENERATION_CONTENT_MISMATCH", retryable=False)
                chunk_rows = existing
            else:
                chunk_rows = [
                    KnowledgeChunk(
                        workspace_id=claim.workspace_id,
                        generation_id=context.generation.id,
                        position=item.position,
                        content=item.content,
                        content_sha256=item.content_sha256,
                        source_locator=item.source_locator,
                        metadata_json={"document_version_id": context.version.id},
                    )
                    for item in parsed
                ]
                session.add_all(chunk_rows)
                await session.flush()
            mappings = list(
                (
                    await session.scalars(
                        select(KnowledgeChunkEmbedding).where(
                            KnowledgeChunkEmbedding.workspace_id == claim.workspace_id,
                            KnowledgeChunkEmbedding.chunk_id.in_([row.id for row in chunk_rows]),
                            KnowledgeChunkEmbedding.embedding_profile_id == context.profile.id,
                        )
                    )
                ).all()
            )
            mapping_by_chunk = {mapping.chunk_id: mapping for mapping in mappings}
            for row in chunk_rows:
                if row.id not in mapping_by_chunk:
                    point_id = uuid5(
                        POINT_NAMESPACE,
                        f"{context.profile.id}:{claim.workspace_id}:{row.id}:"
                        f"{context.generation.id}",
                    )
                    mapping = KnowledgeChunkEmbedding(
                        workspace_id=claim.workspace_id,
                        chunk_id=row.id,
                        embedding_profile_id=context.profile.id,
                        qdrant_point_id=point_id,
                        content_hash=row.content_sha256,
                    )
                    session.add(mapping)
                    mapping_by_chunk[row.id] = mapping
            await session.flush()
            return [
                ChunkWork(
                    chunk_id=row.id,
                    position=row.position,
                    content=row.content,
                    content_hash=row.content_sha256,
                    point_id=mapping_by_chunk[row.id].qdrant_point_id,
                )
                for row in chunk_rows
            ]

    async def _mark_indexed(self, claim: ClaimedJob, batch: list[ChunkWork]) -> None:
        now = datetime.now(UTC)
        async with self.session_factory() as session, session.begin():
            await self._assert_fence(session, claim)
            await session.execute(
                update(KnowledgeChunkEmbedding)
                .where(
                    KnowledgeChunkEmbedding.workspace_id == claim.workspace_id,
                    KnowledgeChunkEmbedding.chunk_id.in_([chunk.chunk_id for chunk in batch]),
                )
                .values(status="indexed", indexed_at=now, error_code=None)
            )

    async def _cutover(self, claim: ClaimedJob, context: IngestionContext) -> None:
        now = datetime.now(UTC)
        async with self.session_factory() as session, session.begin():
            job = await session.scalar(
                select(IngestionJob)
                .where(
                    IngestionJob.id == claim.job_id,
                    IngestionJob.workspace_id == claim.workspace_id,
                )
                .with_for_update()
            )
            if (
                job is None
                or job.status != "processing"
                or job.lease_token != claim.lease_token
                or job.lease_version != claim.lease_version
            ):
                raise LeaseLost
            document = await session.scalar(
                select(KnowledgeDocument)
                .where(
                    KnowledgeDocument.id == context.document.id,
                    KnowledgeDocument.workspace_id == claim.workspace_id,
                )
                .with_for_update()
            )
            knowledge_base = await session.scalar(
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.id == context.knowledge_base.id,
                    KnowledgeBase.workspace_id == claim.workspace_id,
                )
                .with_for_update()
            )
            generation = await session.scalar(
                select(KnowledgeGeneration)
                .where(
                    KnowledgeGeneration.id == context.generation.id,
                    KnowledgeGeneration.workspace_id == claim.workspace_id,
                )
                .with_for_update()
            )
            if document is None or knowledge_base is None or generation is None:
                raise IngestionFailure("INGESTION_STATE_INVALID", retryable=False)
            if document.status != "active" or knowledge_base.status != "active":
                generation.status = "revoked"
                job.status = "cancelled"
                job.lease_token = None
                job.lease_version += 1
                job.last_error_code = "KNOWLEDGE_SOURCE_REVOKED"
                job.completed_at = now
                return
            remaining = int(
                await session.scalar(
                    select(func.count(KnowledgeChunkEmbedding.id))
                    .join(
                        KnowledgeChunk,
                        and_(
                            KnowledgeChunk.workspace_id
                            == KnowledgeChunkEmbedding.workspace_id,
                            KnowledgeChunk.id == KnowledgeChunkEmbedding.chunk_id,
                        ),
                    )
                    .where(
                        KnowledgeChunk.workspace_id == claim.workspace_id,
                        KnowledgeChunk.generation_id == generation.id,
                        KnowledgeChunkEmbedding.status != "indexed",
                    )
                )
                or 0
            )
            if remaining:
                raise IngestionFailure("GENERATION_INDEX_INCOMPLETE", retryable=True)
            generation.status = "ready"
            generation.ready_at = now
            if knowledge_base.active_embedding_profile_id == generation.embedding_profile_id:
                active = await session.scalar(
                    select(KnowledgeDocumentActiveGeneration)
                    .where(
                        KnowledgeDocumentActiveGeneration.workspace_id == claim.workspace_id,
                        KnowledgeDocumentActiveGeneration.document_id == document.id,
                    )
                    .with_for_update()
                )
                if active is None:
                    session.add(
                        KnowledgeDocumentActiveGeneration(
                            workspace_id=claim.workspace_id,
                            document_id=document.id,
                            generation_id=generation.id,
                            activated_at=now,
                        )
                    )
                else:
                    if active.generation_id != generation.id:
                        await session.execute(
                            update(KnowledgeGeneration)
                            .where(
                                KnowledgeGeneration.id == active.generation_id,
                                KnowledgeGeneration.workspace_id == claim.workspace_id,
                            )
                            .values(status="revoked")
                        )
                        old_chunk_ids = select(KnowledgeChunk.id).where(
                            KnowledgeChunk.workspace_id == claim.workspace_id,
                            KnowledgeChunk.generation_id == active.generation_id,
                        )
                        await session.execute(
                            update(KnowledgeChunkEmbedding)
                            .where(
                                KnowledgeChunkEmbedding.workspace_id == claim.workspace_id,
                                KnowledgeChunkEmbedding.chunk_id.in_(old_chunk_ids),
                                KnowledgeChunkEmbedding.status != "deleted",
                            )
                            .values(status="deleting")
                        )
                    active.generation_id = generation.id
                    active.activated_at = now
            elif knowledge_base.target_embedding_profile_id != generation.embedding_profile_id:
                raise IngestionFailure("EMBEDDING_PROFILE_NOT_ASSIGNED", retryable=False)
            job.status = "succeeded"
            job.retryable = False
            job.last_error_code = None
            job.lease_token = None
            job.lease_expires_at = None
            job.completed_at = now
            job.updated_at = now
            await session.execute(
                update(IngestionJobAttempt)
                .where(
                    IngestionJobAttempt.job_id == job.id,
                    IngestionJobAttempt.attempt_no == claim.attempt_no,
                )
                .values(status="succeeded", finished_at=now)
            )

    async def _record_failure(
        self, claim: ClaimedJob, error_code: str, *, retryable: bool
    ) -> None:
        now = datetime.now(UTC)
        async with self.session_factory() as session, session.begin():
            job = await session.scalar(
                select(IngestionJob)
                .where(
                    IngestionJob.id == claim.job_id,
                    IngestionJob.workspace_id == claim.workspace_id,
                )
                .with_for_update()
            )
            if (
                job is None
                or job.status != "processing"
                or job.lease_token != claim.lease_token
                or job.lease_version != claim.lease_version
            ):
                return
            may_retry = retryable and job.attempts < self.settings.knowledge_job_max_attempts
            job.status = "retry_scheduled" if may_retry else "failed"
            job.retryable = retryable
            job.last_error_code = error_code
            job.lease_token = None
            job.lease_expires_at = None
            job.updated_at = now
            if may_retry:
                ceiling = min(
                    self.settings.knowledge_retry_max_seconds,
                    self.settings.knowledge_retry_base_seconds * (2 ** (job.attempts - 1)),
                )
                job.scheduled_at = now + timedelta(seconds=secrets.randbelow(ceiling + 1))
            else:
                job.completed_at = now
                if job.target_generation_id is not None:
                    await session.execute(
                        update(KnowledgeGeneration)
                        .where(
                            KnowledgeGeneration.id == job.target_generation_id,
                            KnowledgeGeneration.workspace_id == claim.workspace_id,
                        )
                        .values(status="failed", failure_code=error_code)
                    )
                    failed_chunk_ids = select(KnowledgeChunk.id).where(
                        KnowledgeChunk.workspace_id == claim.workspace_id,
                        KnowledgeChunk.generation_id == job.target_generation_id,
                    )
                    await session.execute(
                        update(KnowledgeChunkEmbedding)
                        .where(
                            KnowledgeChunkEmbedding.workspace_id == claim.workspace_id,
                            KnowledgeChunkEmbedding.chunk_id.in_(failed_chunk_ids),
                            KnowledgeChunkEmbedding.status != "deleted",
                        )
                        .values(status="deleting", error_code=error_code)
                    )
            await session.execute(
                update(IngestionJobAttempt)
                .where(
                    IngestionJobAttempt.job_id == job.id,
                    IngestionJobAttempt.attempt_no == claim.attempt_no,
                )
                .values(status="failed", error_code=error_code, finished_at=now)
            )
