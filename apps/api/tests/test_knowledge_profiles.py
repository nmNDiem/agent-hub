import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_hub_api.core.config import Settings
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.models import User
from agent_hub_api.knowledge.ingestion import KnowledgeIngestionWorker
from agent_hub_api.knowledge.models import (
    EmbeddingProfile,
    IngestionJob,
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeDocumentActiveGeneration,
    KnowledgeDocumentVersion,
    KnowledgeGeneration,
)
from agent_hub_api.knowledge.profiles import (
    EmbeddingProfileConfiguration,
    KnowledgeProfileService,
)
from agent_hub_api.knowledge.providers import (
    EmbeddingProfileSpec,
    ProviderTemporaryError,
    VectorPoint,
    VectorSearchHit,
)
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import Workspace


class FakeStorage:
    async def upload_file(self, *, object_key: str, source: Path, content_type: str) -> None:
        raise AssertionError("manual source does not upload")

    async def download_file(
        self, *, object_key: str, destination: Path, max_bytes: int
    ) -> None:
        raise AssertionError("manual source does not download")

    async def delete(self, *, object_key: str) -> None:
        pass


class FakeEmbeddingProvider:
    async def embed(
        self, profile: EmbeddingProfileSpec, texts: list[str]
    ) -> list[tuple[float, ...]]:
        return [tuple(float(index) for index in range(profile.dimensions)) for _ in texts]


class FakeVectorIndex:
    def __init__(self) -> None:
        self.ensured: list[int] = []
        self.points: dict[UUID, VectorPoint] = {}

    async def ensure_profile(self, profile: EmbeddingProfileSpec) -> None:
        self.ensured.append(profile.id)

    async def upsert(
        self, profile: EmbeddingProfileSpec, points: list[VectorPoint]
    ) -> None:
        self.points.update({point.point_id: point for point in points})

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

    async def delete(self, profile: EmbeddingProfileSpec, point_ids: list[UUID]) -> None:
        for point_id in point_ids:
            self.points.pop(point_id, None)


class FailingEnsureVectorIndex(FakeVectorIndex):
    async def ensure_profile(self, profile: EmbeddingProfileSpec) -> None:
        raise ProviderTemporaryError("offline")


async def seed_awaiting_job(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[UUID, int, int]:
    workspace_id = new_uuid_v7()
    user_id = new_uuid_v7()
    async with sessions() as session, session.begin():
        session.add(
            User(
                id=user_id,
                normalized_email=f"profile-{user_id}@example.test",
                password_hash="test",
                status="active",
            )
        )
        session.add(
            Workspace(
                id=workspace_id,
                slug=f"profile-{workspace_id}",
                display_name="Profile test",
                status="active",
            )
        )
        knowledge_base = KnowledgeBase(
            workspace_id=workspace_id,
            name="Profile base",
            kind="general",
        )
        session.add(knowledge_base)
        await session.flush()
        document = KnowledgeDocument(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base.id,
            title="Returns",
            kind="policy",
        )
        session.add(document)
        await session.flush()
        version = KnowledgeDocumentVersion(
            workspace_id=workspace_id,
            document_id=document.id,
            version_no=1,
            source_kind="manual",
            source_text="Returns are accepted within seven days.",
            content_sha256="a" * 64,
            mime_type="text/plain",
            byte_size=39,
            created_by_user_id=user_id,
        )
        session.add(version)
        await session.flush()
        job = IngestionJob(
            workspace_id=workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            status="awaiting_profile",
            idempotency_key="initial-awaiting-profile",
            request_sha256="b" * 64,
        )
        session.add(job)
        await session.flush()
        return workspace_id, knowledge_base.id, job.id


def config(*, model: str, dimensions: int, collection: str) -> EmbeddingProfileConfiguration:
    return EmbeddingProfileConfiguration(
        provider="openai",
        model=model,
        dimensions=dimensions,
        provider_model_revision=None,
        pipeline_version="test-v1",
        distance_metric="cosine",
        collection=collection,
    )


def test_profile_activation_rebuild_and_atomic_migration(tmp_path: Path) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'profiles.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            workspace_id, base_id, initial_job_id = await seed_awaiting_job(sessions)
            settings = Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                knowledge_chunk_size=40,
                knowledge_chunk_overlap=5,
                knowledge_job_heartbeat_seconds=1,
                knowledge_job_lease_seconds=10,
            )
            vectors = FakeVectorIndex()
            profiles = KnowledgeProfileService(
                session_factory=sessions,
                settings=settings,
                vector_index=vectors,
            )
            first = await profiles.bootstrap(
                config(model="test-3d", dimensions=3, collection="profile-test-3d")
            )
            assert first.status == "active"
            unavailable_profiles = KnowledgeProfileService(
                session_factory=sessions,
                settings=settings,
                vector_index=FailingEnsureVectorIndex(),
            )
            with pytest.raises(ProviderTemporaryError):
                await unavailable_profiles.bootstrap(
                    config(model="test-3d", dimensions=3, collection="profile-test-3d")
                )
            async with sessions() as session:
                still_active = await session.get(EmbeddingProfile, first.id)
                assert still_active is not None and still_active.status == "active"
            assert await profiles.activate_unprofiled_bases(
                profile_id=first.id, workspace_id=workspace_id
            ) == 1
            async with sessions() as session:
                job = await session.get(IngestionJob, initial_job_id)
                assert job is not None and job.status == "queued"
                assert job.target_generation_id is not None

            worker = KnowledgeIngestionWorker(
                session_factory=sessions,
                settings=settings,
                storage=FakeStorage(),
                embedding_provider=FakeEmbeddingProvider(),
                vector_index=vectors,
            )
            assert await worker.run_once() is True
            assert vectors.points

            assert await profiles.queue_rebuild(
                profile_id=first.id,
                operation_id="rebuild-1",
                workspace_id=workspace_id,
            ) == 1
            assert await worker.run_once() is True
            assert await profiles.queue_rebuild(
                profile_id=first.id,
                operation_id="rebuild-1",
                workspace_id=workspace_id,
            ) == 0

            second = await profiles.bootstrap(
                config(model="test-4d", dimensions=4, collection="profile-test-4d")
            )
            assert await profiles.start_migration(
                workspace_id=workspace_id,
                knowledge_base_id=base_id,
                target_profile_id=second.id,
                operation_id="migration-1",
            ) == 1
            assert await worker.run_once() is True

            async with sessions() as session:
                base = await session.get(KnowledgeBase, base_id)
                assert base is not None
                assert base.active_embedding_profile_id == first.id
                assert base.target_embedding_profile_id == second.id

            assert await profiles.promote(
                workspace_id=workspace_id,
                knowledge_base_id=base_id,
            ) == 1
            async with sessions() as session:
                base = await session.get(KnowledgeBase, base_id)
                assert base is not None
                assert base.active_embedding_profile_id == second.id
                assert base.target_embedding_profile_id is None
                active = await session.scalar(
                    select(KnowledgeDocumentActiveGeneration).where(
                        KnowledgeDocumentActiveGeneration.workspace_id == workspace_id
                    )
                )
                assert active is not None
                active_generation = await session.get(KnowledgeGeneration, active.generation_id)
                assert active_generation is not None
                assert active_generation.embedding_profile_id == second.id
                old_ready = list(
                    await session.scalars(
                        select(KnowledgeGeneration).where(
                            KnowledgeGeneration.workspace_id == workspace_id,
                            KnowledgeGeneration.embedding_profile_id == first.id,
                            KnowledgeGeneration.status == "ready",
                        )
                    )
                )
                assert old_ready
        finally:
            await engine.dispose()

    asyncio.run(exercise())
