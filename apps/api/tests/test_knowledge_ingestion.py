import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agent_hub_api.core.config import Settings
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.models import User
from agent_hub_api.knowledge.extraction import ExtractionError, ExtractionLimits, extract_pdf
from agent_hub_api.knowledge.ingestion import KnowledgeIngestionWorker, LeaseLost
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
from agent_hub_api.knowledge.providers import (
    EmbeddingProfileSpec,
    ProviderTemporaryError,
    VectorPoint,
    VectorSearchHit,
)
from agent_hub_api.knowledge.reconcile import KnowledgeReconciler
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import Workspace


class FakeStorage:
    async def upload_file(self, *, object_key: str, source: Path, content_type: str) -> None:
        raise AssertionError("manual ingestion must not upload")

    async def download_file(
        self, *, object_key: str, destination: Path, max_bytes: int
    ) -> None:
        raise AssertionError("manual ingestion must not download")

    async def delete(self, *, object_key: str) -> None:
        pass


class FakeEmbeddingProvider:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0

    async def embed(
        self, profile: EmbeddingProfileSpec, texts: list[str]
    ) -> list[tuple[float, ...]]:
        self.calls += 1
        if self.failures:
            self.failures -= 1
            raise ProviderTemporaryError("temporary test failure")
        return [tuple(float(index) for index in range(profile.dimensions)) for _ in texts]


class FakeVectorIndex:
    def __init__(self, *, delete_failures: int = 0) -> None:
        self.points: dict[object, VectorPoint] = {}
        self.delete_failures = delete_failures

    async def ensure_profile(self, profile: EmbeddingProfileSpec) -> None:
        pass

    async def upsert(
        self, profile: EmbeddingProfileSpec, points: list[VectorPoint]
    ) -> None:
        self.points.update({point.point_id: point for point in points})

    async def delete(self, profile: EmbeddingProfileSpec, point_ids: list[UUID]) -> None:
        if self.delete_failures:
            self.delete_failures -= 1
            raise ProviderTemporaryError("temporary delete failure")
        for point_id in point_ids:
            self.points.pop(point_id, None)

    async def search(
        self,
        profile: EmbeddingProfileSpec,
        vector: tuple[float, ...],
        *,
        workspace_id: UUID,
        allowed_knowledge_base_ids: tuple[int, ...],
        limit: int,
    ) -> list[VectorSearchHit]:
        return []


async def seed_job(
    session_factory: async_sessionmaker[Any], *, content: str
) -> tuple[UUID, int]:
    workspace_id = new_uuid_v7()
    user_id = new_uuid_v7()
    async with session_factory() as session, session.begin():
        session.add(
            User(
                id=user_id,
                normalized_email=f"worker-{user_id}@example.test",
                password_hash="test",
                status="active",
            )
        )
        session.add(
            Workspace(
                id=workspace_id,
                slug=f"worker-{workspace_id}",
                display_name="Worker",
                status="active",
            )
        )
        profile = EmbeddingProfile(
            provider="fake",
            model="fake-3d",
            dimensions=3,
            pipeline_version="test-v1",
            distance_metric="cosine",
            qdrant_collection=f"test-{workspace_id}",
            config_hash=str(workspace_id).replace("-", "") + "0" * 32,
            status="active",
        )
        session.add(profile)
        await session.flush()
        knowledge_base = KnowledgeBase(
            workspace_id=workspace_id,
            name="Worker base",
            kind="general",
            active_embedding_profile_id=profile.id,
        )
        session.add(knowledge_base)
        await session.flush()
        document = KnowledgeDocument(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base.id,
            title="Manual",
            kind="faq",
        )
        session.add(document)
        await session.flush()
        version = KnowledgeDocumentVersion(
            workspace_id=workspace_id,
            document_id=document.id,
            version_no=1,
            source_kind="manual",
            source_text=content,
            content_sha256="a" * 64,
            mime_type="text/plain",
            byte_size=len(content.encode()),
            created_by_user_id=user_id,
        )
        session.add(version)
        await session.flush()
        from agent_hub_api.knowledge.models import KnowledgeGeneration

        generation = KnowledgeGeneration(
            workspace_id=workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            embedding_profile_id=profile.id,
            generation_no=1,
            chunker_version="char-paragraph-v1",
            chunk_size=40,
            chunk_overlap=5,
            pipeline_config_hash="b" * 64,
        )
        session.add(generation)
        await session.flush()
        job = IngestionJob(
            workspace_id=workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            target_generation_id=generation.id,
            status="queued",
            idempotency_key="worker-test",
            request_sha256="c" * 64,
        )
        session.add(job)
        await session.flush()
        return workspace_id, job.id


def test_worker_persists_chunks_indexes_and_cuts_over(tmp_path: Path) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            workspace_id, job_id = await seed_job(
                session_factory,
                content=(
                    "Returns are accepted within seven days.\n\n"
                    "Products must retain their original labels."
                ),
            )
            vectors = FakeVectorIndex()
            worker = KnowledgeIngestionWorker(
                session_factory=session_factory,
                settings=Settings(
                    app_env="test",
                    jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                    knowledge_job_heartbeat_seconds=1,
                    knowledge_job_lease_seconds=10,
                    knowledge_embedding_batch_size=2,
                ),
                storage=FakeStorage(),
                embedding_provider=FakeEmbeddingProvider(),
                vector_index=vectors,
            )
            assert await worker.run_once() is True
            async with session_factory() as session:
                job = await session.get(IngestionJob, job_id)
                assert job is not None and job.status == "succeeded"
                chunks = list(
                    await session.scalars(
                        select(KnowledgeChunk).where(
                            KnowledgeChunk.workspace_id == workspace_id
                        )
                    )
                )
                embeddings = list(
                    await session.scalars(
                        select(KnowledgeChunkEmbedding).where(
                            KnowledgeChunkEmbedding.workspace_id == workspace_id
                        )
                    )
                )
                active = await session.scalar(
                    select(KnowledgeDocumentActiveGeneration).where(
                        KnowledgeDocumentActiveGeneration.workspace_id == workspace_id
                    )
                )
                assert len(chunks) >= 2
                assert len(embeddings) == len(chunks)
                assert all(item.status == "indexed" for item in embeddings)
                assert active is not None
                assert len(vectors.points) == len(chunks)
                assert all(
                    point.payload["workspace_id"] == str(workspace_id)
                    for point in vectors.points.values()
                )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_worker_schedules_transient_failure_without_cutover(tmp_path: Path) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retry.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            _, job_id = await seed_job(session_factory, content="Temporary provider failure.")
            worker = KnowledgeIngestionWorker(
                session_factory=session_factory,
                settings=Settings(
                    app_env="test",
                    jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                ),
                storage=FakeStorage(),
                embedding_provider=FakeEmbeddingProvider(failures=1),
                vector_index=FakeVectorIndex(),
            )
            assert await worker.run_once() is True
            async with session_factory() as session:
                job = await session.get(IngestionJob, job_id)
                assert job is not None
                assert job.status == "retry_scheduled"
                assert job.retryable is True
                assert job.last_error_code == "INGESTION_PROVIDER_UNAVAILABLE"
                active = await session.scalar(select(KnowledgeDocumentActiveGeneration))
                assert active is None
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_expired_worker_is_fenced_after_lease_takeover(tmp_path: Path) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'fencing.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            _, _ = await seed_job(session_factory, content="Fencing token test.")
            worker = KnowledgeIngestionWorker(
                session_factory=session_factory,
                settings=Settings(
                    app_env="test",
                    jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                ),
                storage=FakeStorage(),
                embedding_provider=FakeEmbeddingProvider(),
                vector_index=FakeVectorIndex(),
            )
            stale_claim = await worker.claim_next()
            assert stale_claim is not None
            async with session_factory() as session, session.begin():
                await session.execute(
                    update(IngestionJob)
                    .where(IngestionJob.id == stale_claim.job_id)
                    .values(
                        lease_token=uuid4(),
                        lease_version=stale_claim.lease_version + 1,
                    )
                )
            assert await worker.heartbeat(stale_claim) is False
            with pytest.raises(LeaseLost):
                await worker._context(stale_claim)  # noqa: SLF001
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_reconciler_deletes_vectors_from_revoked_generation(tmp_path: Path) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reconcile.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            workspace_id, _ = await seed_job(session_factory, content="Reconcile this content.")
            vectors = FakeVectorIndex()
            settings = Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
            )
            worker = KnowledgeIngestionWorker(
                session_factory=session_factory,
                settings=settings,
                storage=FakeStorage(),
                embedding_provider=FakeEmbeddingProvider(),
                vector_index=vectors,
            )
            assert await worker.run_once() is True
            assert vectors.points
            async with session_factory() as session, session.begin():
                generation = await session.scalar(
                    select(KnowledgeGeneration).where(
                        KnowledgeGeneration.workspace_id == workspace_id
                    )
                )
                assert generation is not None
                generation.status = "revoked"
            reconciler = KnowledgeReconciler(
                session_factory=session_factory,
                settings=settings,
                storage=FakeStorage(),
                vector_index=vectors,
            )
            assert await reconciler.run_once() is True
            assert vectors.points == {}
            async with session_factory() as session:
                statuses = list(
                    await session.scalars(
                        select(KnowledgeChunkEmbedding.status).where(
                            KnowledgeChunkEmbedding.workspace_id == workspace_id
                        )
                    )
                )
                assert statuses and set(statuses) == {"deleted"}
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_reconciler_defers_vector_cleanup_during_qdrant_outage(tmp_path: Path) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'outage.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            workspace_id, _ = await seed_job(session_factory, content="Deferred cleanup.")
            vectors = FakeVectorIndex(delete_failures=1)
            settings = Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
            )
            worker = KnowledgeIngestionWorker(
                session_factory=session_factory,
                settings=settings,
                storage=FakeStorage(),
                embedding_provider=FakeEmbeddingProvider(),
                vector_index=vectors,
            )
            assert await worker.run_once() is True
            async with session_factory() as session, session.begin():
                generation = await session.scalar(
                    select(KnowledgeGeneration).where(
                        KnowledgeGeneration.workspace_id == workspace_id
                    )
                )
                assert generation is not None
                generation.status = "revoked"
            reconciler = KnowledgeReconciler(
                session_factory=session_factory,
                settings=settings,
                storage=FakeStorage(),
                vector_index=vectors,
            )
            assert await reconciler.run_once() is False
            async with session_factory() as session:
                statuses = set(
                    await session.scalars(
                        select(KnowledgeChunkEmbedding.status).where(
                            KnowledgeChunkEmbedding.workspace_id == workspace_id
                        )
                    )
                )
                assert statuses == {"deleting"}
            assert await reconciler.run_once() is True
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_pdf_sandbox_rejects_malformed_and_encrypted_files(tmp_path: Path) -> None:
    limits = ExtractionLimits(
        max_pages=10,
        max_chars=10_000,
        wall_seconds=5,
        cpu_seconds=3,
        memory_bytes=256 * 1024 * 1024,
        output_bytes=1024 * 1024,
    )
    malformed = tmp_path / "malformed.pdf"
    malformed.write_bytes(b"%PDF-1.7\nmalformed")
    with pytest.raises(ExtractionError, match="PDF_INVALID"):
        asyncio.run(extract_pdf(malformed, limits))

    encrypted = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    with encrypted.open("wb") as output:
        writer.write(output)
    with pytest.raises(ExtractionError, match="PDF_ENCRYPTED_UNSUPPORTED"):
        asyncio.run(extract_pdf(encrypted, limits))


def test_pdf_sandbox_bounds_historical_inline_image_and_wall_time(tmp_path: Path) -> None:
    bomb = tmp_path / "inline-image.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    stream = DecodedStreamObject()
    stream.set_data(b"q BI /W 1 /H 1 /CS /RGB /BPC 8 ID abc")
    page[NameObject("/Contents")] = writer._add_object(stream)  # noqa: SLF001
    with bomb.open("wb") as output:
        writer.write(output)
    limits = ExtractionLimits(
        max_pages=10,
        max_chars=10_000,
        wall_seconds=3,
        cpu_seconds=2,
        memory_bytes=256 * 1024 * 1024,
        output_bytes=1024 * 1024,
    )
    with pytest.raises(ExtractionError) as result:
        asyncio.run(extract_pdf(bomb, limits))
    assert result.value.code in {"PDF_INVALID", "PDF_TEXT_NOT_FOUND"}

    sleeping_child = tmp_path / "sleeping_child.py"
    sleeping_child.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    short_limits = ExtractionLimits(
        max_pages=10,
        max_chars=10_000,
        wall_seconds=1,
        cpu_seconds=5,
        memory_bytes=256 * 1024 * 1024,
        output_bytes=1024 * 1024,
    )
    with pytest.raises(ExtractionError, match="PDF_PARSE_TIMEOUT"):
        asyncio.run(extract_pdf(bomb, short_limits, child_script=sleeping_child))
