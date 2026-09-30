import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_hub_api.agents.models import Agent
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.models import User
from agent_hub_api.knowledge.models import (
    AgentKnowledgeBase,
    EmbeddingProfile,
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
from agent_hub_api.knowledge.retrieval import (
    KnowledgeRetrievalService,
    KnowledgeRetrievalUnavailable,
    resolve_agent_knowledge_scope,
)
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import Workspace


class FakeEmbeddingProvider:
    async def embed(
        self, profile: EmbeddingProfileSpec, texts: list[str]
    ) -> list[tuple[float, ...]]:
        return [(1.0, 0.0, 0.0) for _ in texts]


class FailingEmbeddingProvider:
    async def embed(
        self, profile: EmbeddingProfileSpec, texts: list[str]
    ) -> list[tuple[float, ...]]:
        raise ProviderTemporaryError("offline")


class FakeVectorIndex:
    def __init__(self, hits: list[VectorSearchHit]) -> None:
        self.hits = hits
        self.searches: list[tuple[UUID, tuple[int, ...]]] = []

    async def ensure_profile(self, profile: EmbeddingProfileSpec) -> None:
        pass

    async def upsert(
        self, profile: EmbeddingProfileSpec, points: list[VectorPoint]
    ) -> None:
        pass

    async def search(
        self,
        profile: EmbeddingProfileSpec,
        vector: tuple[float, ...],
        *,
        workspace_id: UUID,
        allowed_knowledge_base_ids: tuple[int, ...],
        limit: int,
    ) -> list[VectorSearchHit]:
        self.searches.append((workspace_id, allowed_knowledge_base_ids))
        return self.hits[:limit]

    async def delete(self, profile: EmbeddingProfileSpec, point_ids: list[UUID]) -> None:
        pass


@dataclass(frozen=True)
class SeededSource:
    workspace_id: UUID
    agent_public_id: UUID
    generation_id: int
    hit: VectorSearchHit


async def seed_source(
    sessions: async_sessionmaker[AsyncSession], *, suffix: str
) -> SeededSource:
    workspace_id = new_uuid_v7()
    user_id = new_uuid_v7()
    agent_public_id = new_uuid_v7()
    point_id = uuid4()
    async with sessions() as session, session.begin():
        session.add(
            User(
                id=user_id,
                normalized_email=f"retrieval-{suffix}@example.test",
                password_hash="test",
                status="active",
            )
        )
        session.add(
            Workspace(
                id=workspace_id,
                slug=f"retrieval-{suffix}",
                display_name=f"Retrieval {suffix}",
                status="active",
            )
        )
        profile = EmbeddingProfile(
            provider="openai",
            model="test-3d",
            dimensions=3,
            pipeline_version="test-v1",
            distance_metric="cosine",
            qdrant_collection=f"retrieval-{suffix}",
            config_hash=(suffix * 64)[:64],
            status="active",
        )
        session.add(profile)
        await session.flush()
        knowledge_base = KnowledgeBase(
            workspace_id=workspace_id,
            name=f"Base {suffix}",
            kind="general",
            active_embedding_profile_id=profile.id,
        )
        agent = Agent(
            public_id=agent_public_id,
            workspace_id=workspace_id,
            name=f"Agent {suffix}",
            default_locale="vi",
            created_by_user_id=user_id,
        )
        session.add_all([knowledge_base, agent])
        await session.flush()
        session.add(
            AgentKnowledgeBase(
                workspace_id=workspace_id,
                agent_id=agent.id,
                knowledge_base_id=knowledge_base.id,
            )
        )
        document = KnowledgeDocument(
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base.id,
            title=f"Policy {suffix}",
            kind="policy",
        )
        session.add(document)
        await session.flush()
        version = KnowledgeDocumentVersion(
            workspace_id=workspace_id,
            document_id=document.id,
            version_no=1,
            source_kind="manual",
            source_text="Returns within seven days.",
            content_sha256=suffix * 64,
            mime_type="text/plain",
            byte_size=26,
            created_by_user_id=user_id,
        )
        session.add(version)
        await session.flush()
        generation = KnowledgeGeneration(
            workspace_id=workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            embedding_profile_id=profile.id,
            generation_no=1,
            status="ready",
            chunker_version="test-v1",
            chunk_size=100,
            chunk_overlap=10,
            pipeline_config_hash="f" * 64,
        )
        session.add(generation)
        await session.flush()
        chunk = KnowledgeChunk(
            workspace_id=workspace_id,
            generation_id=generation.id,
            position=0,
            content="Returns within seven days.",
            content_sha256=suffix * 64,
            source_locator=f"document:{document.id}:version:1:chars:0-26",
            metadata_json={},
        )
        session.add(chunk)
        await session.flush()
        session.add_all(
            [
                KnowledgeChunkEmbedding(
                    workspace_id=workspace_id,
                    chunk_id=chunk.id,
                    embedding_profile_id=profile.id,
                    qdrant_point_id=point_id,
                    content_hash=chunk.content_sha256,
                    status="indexed",
                ),
                KnowledgeDocumentActiveGeneration(
                    workspace_id=workspace_id,
                    document_id=document.id,
                    generation_id=generation.id,
                ),
            ]
        )
        payload: dict[str, str | int] = {
            "workspace_id": str(workspace_id),
            "knowledge_base_id": knowledge_base.id,
            "document_id": document.id,
            "document_version_id": version.id,
            "generation_id": generation.id,
            "generation": generation.generation_no,
            "chunk_id": chunk.id,
            "embedding_profile_id": profile.id,
            "content_hash": chunk.content_sha256,
        }
        return SeededSource(
            workspace_id=workspace_id,
            agent_public_id=agent_public_id,
            generation_id=generation.id,
            hit=VectorSearchHit(point_id=point_id, score=0.95, payload=payload),
        )


def test_retrieval_revalidates_qdrant_hits_and_rejects_cross_workspace_stale_data(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retrieval.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            source_a = await seed_source(sessions, suffix="a")
            source_b = await seed_source(sessions, suffix="b")

            vectors = FakeVectorIndex([source_b.hit, source_a.hit])
            async with sessions() as session:
                scope = await resolve_agent_knowledge_scope(
                    session,
                    workspace_id=source_a.workspace_id,
                    public_agent_id=source_a.agent_public_id,
                )
                results = await KnowledgeRetrievalService(
                    session,
                    embedding_provider=FakeEmbeddingProvider(),
                    vector_index=vectors,
                ).search(scope, "return policy")
                assert len(results) == 1
                assert results[0].citation.document_title == "Policy a"
                assert vectors.searches == [
                    (source_a.workspace_id, scope.allowed_knowledge_base_ids)
                ]

                with pytest.raises(ApiError) as denied:
                    await resolve_agent_knowledge_scope(
                        session,
                        workspace_id=source_b.workspace_id,
                        public_agent_id=source_a.agent_public_id,
                    )
                assert denied.value.status_code == 404

            async with sessions() as session, session.begin():
                generation = await session.get(KnowledgeGeneration, source_a.generation_id)
                assert generation is not None
                generation.status = "revoked"
            async with sessions() as session:
                scope = await resolve_agent_knowledge_scope(
                    session,
                    workspace_id=source_a.workspace_id,
                    public_agent_id=source_a.agent_public_id,
                )
                assert (
                    await KnowledgeRetrievalService(
                        session,
                        embedding_provider=FakeEmbeddingProvider(),
                        vector_index=vectors,
                    ).search(scope, "return policy")
                    == []
                )
        finally:
            await engine.dispose()

    asyncio.run(exercise())


def test_retrieval_surfaces_provider_outage(tmp_path: Path) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'outage.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            source = await seed_source(sessions, suffix="c")
            async with sessions() as session:
                scope = await resolve_agent_knowledge_scope(
                    session,
                    workspace_id=source.workspace_id,
                    public_agent_id=source.agent_public_id,
                )
                with pytest.raises(KnowledgeRetrievalUnavailable):
                    await KnowledgeRetrievalService(
                        session,
                        embedding_provider=FailingEmbeddingProvider(),
                        vector_index=FakeVectorIndex([source.hit]),
                    ).search(scope, "return policy")
        finally:
            await engine.dispose()

    asyncio.run(exercise())
