import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agent_hub_api.core.config import Settings
from agent_hub_api.knowledge.models import (
    EmbeddingProfile,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeDocumentActiveGeneration,
    KnowledgeDocumentVersion,
    KnowledgeGeneration,
)
from agent_hub_api.knowledge.providers import EmbeddingProfileSpec, VectorPoint
from agent_hub_api.knowledge.qdrant_index import QdrantKnowledgeVectorIndex
from agent_hub_api.knowledge.retrieval import (
    AuthorizedKnowledgeScope,
    KnowledgeRetrievalService,
)
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import Workspace


class DeterministicEmbeddingProvider:
    async def embed(
        self, profile: EmbeddingProfileSpec, texts: list[str]
    ) -> list[tuple[float, ...]]:
        return [(1.0, 0.0, 0.0) for _ in texts]


def qdrant_settings() -> Settings:
    repository_env = Path(__file__).resolve().parents[3] / ".env"
    load_dotenv(repository_env, override=False)
    settings = Settings()
    if os.getenv("RUN_QDRANT_INTEGRATION_TESTS") != "true":
        pytest.skip("Set RUN_QDRANT_INTEGRATION_TESTS=true to use non-production Qdrant")
    if settings.app_env not in {"local", "test"}:
        pytest.fail("Qdrant integration tests require APP_ENV=local or test")
    if settings.qdrant_url is None or settings.qdrant_api_key is None:
        pytest.skip("Qdrant Cloud credentials are not configured")
    return settings


@pytest.mark.qdrant
def test_real_qdrant_enforces_filters_and_relational_authority(tmp_path: Path) -> None:
    async def exercise() -> None:
        settings = qdrant_settings()
        collection = f"{settings.qdrant_collection_prefix}_test_{uuid4().hex}"
        if "_test_" not in collection:
            pytest.fail("Refusing to create an unsafe integration-test collection")
        client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout_seconds,
            prefer_grpc=False,
        )
        index = QdrantKnowledgeVectorIndex(client=client)
        profile = EmbeddingProfileSpec(
            id=9_999_999,
            provider="fake",
            model="deterministic-3d",
            dimensions=3,
            provider_model_revision=None,
            pipeline_version="qdrant-integration-v1",
            distance_metric="cosine",
            collection=collection,
            config_hash="f" * 64,
        )
        workspace_a = uuid4()
        workspace_b = uuid4()
        point_a = uuid4()
        point_b = uuid4()
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'qdrant.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as session, session.begin():
                session.add(
                    Workspace(
                        id=workspace_a,
                        slug=f"qdrant-{workspace_a}",
                        display_name="Qdrant integration",
                        status="active",
                    )
                )
                session.add(
                    EmbeddingProfile(
                        id=profile.id,
                        provider=profile.provider,
                        model=profile.model,
                        dimensions=profile.dimensions,
                        pipeline_version=profile.pipeline_version,
                        distance_metric=profile.distance_metric,
                        qdrant_collection=profile.collection,
                        config_hash=profile.config_hash,
                        status="active",
                    )
                )
                session.add(
                    KnowledgeBase(
                        id=101,
                        workspace_id=workspace_a,
                        name="Integration base",
                        kind="general",
                        active_embedding_profile_id=profile.id,
                    )
                )
                session.add(
                    KnowledgeDocument(
                        id=1001,
                        workspace_id=workspace_a,
                        knowledge_base_id=101,
                        title="Integration policy",
                        kind="policy",
                    )
                )
                session.add(
                    KnowledgeDocumentVersion(
                        id=2001,
                        workspace_id=workspace_a,
                        document_id=1001,
                        version_no=1,
                        source_kind="manual",
                        source_text="Cloud-isolated policy.",
                        content_sha256="a" * 64,
                        mime_type="text/plain",
                        byte_size=22,
                        created_by_user_id=uuid4(),
                    )
                )
                session.add(
                    KnowledgeGeneration(
                        id=3001,
                        workspace_id=workspace_a,
                        document_id=1001,
                        document_version_id=2001,
                        embedding_profile_id=profile.id,
                        generation_no=1,
                        status="ready",
                        chunker_version="test-v1",
                        chunk_size=100,
                        chunk_overlap=10,
                        pipeline_config_hash="b" * 64,
                    )
                )
                session.add(
                    KnowledgeChunk(
                        id=4001,
                        workspace_id=workspace_a,
                        generation_id=3001,
                        position=0,
                        content="Cloud-isolated policy.",
                        content_sha256="a" * 64,
                        source_locator="document:1001:version:1:chars:0-22",
                        metadata_json={},
                    )
                )
                session.add(
                    KnowledgeChunkEmbedding(
                        id=5001,
                        workspace_id=workspace_a,
                        chunk_id=4001,
                        embedding_profile_id=profile.id,
                        qdrant_point_id=point_a,
                        content_hash="a" * 64,
                        status="indexed",
                    )
                )
                session.add(
                    KnowledgeDocumentActiveGeneration(
                        workspace_id=workspace_a,
                        document_id=1001,
                        generation_id=3001,
                    )
                )
            await index.ensure_profile(profile)
            await index.upsert(
                profile,
                [
                    VectorPoint(
                        point_id=point_a,
                        vector=(1.0, 0.0, 0.0),
                        payload={
                            "workspace_id": str(workspace_a),
                            "knowledge_base_id": 101,
                            "document_id": 1001,
                            "document_version_id": 2001,
                            "generation_id": 3001,
                            "generation": 1,
                            "chunk_id": 4001,
                            "embedding_profile_id": profile.id,
                            "content_hash": "a" * 64,
                        },
                    ),
                    VectorPoint(
                        point_id=point_b,
                        vector=(1.0, 0.0, 0.0),
                        payload={
                            "workspace_id": str(workspace_b),
                            "knowledge_base_id": 202,
                            "embedding_profile_id": profile.id,
                        },
                    ),
                ],
            )
            hits = await index.search(
                profile,
                (1.0, 0.0, 0.0),
                workspace_id=workspace_a,
                allowed_knowledge_base_ids=(101,),
                limit=10,
            )
            assert [hit.point_id for hit in hits] == [point_a]
            async with sessions() as session:
                scope = AuthorizedKnowledgeScope(workspace_a, (101,))
                retrieved = await KnowledgeRetrievalService(
                    session,
                    embedding_provider=DeterministicEmbeddingProvider(),
                    vector_index=index,
                ).search(scope, "policy")
                assert [item.citation.chunk_id for item in retrieved] == [4001]

            async with sessions() as session, session.begin():
                generation = await session.scalar(
                    select(KnowledgeGeneration).where(KnowledgeGeneration.id == 3001)
                )
                assert generation is not None
                generation.status = "revoked"
            async with sessions() as session:
                assert (
                    await KnowledgeRetrievalService(
                        session,
                        embedding_provider=DeterministicEmbeddingProvider(),
                        vector_index=index,
                    ).search(AuthorizedKnowledgeScope(workspace_a, (101,)), "policy")
                    == []
                )
            assert (
                await index.search(
                    profile,
                    (1.0, 0.0, 0.0),
                    workspace_id=workspace_a,
                    allowed_knowledge_base_ids=(202,),
                    limit=10,
                )
                == []
            )
            await index.upsert(
                profile,
                [
                    VectorPoint(
                        point_id=point_a,
                        vector=(1.0, 0.0, 0.0),
                        payload={
                            "workspace_id": str(workspace_a),
                            "knowledge_base_id": 101,
                            "embedding_profile_id": profile.id,
                        },
                    )
                ],
            )
            await index.delete(profile, [point_a])
            await index.delete(profile, [point_a])
            assert (
                await index.search(
                    profile,
                    (1.0, 0.0, 0.0),
                    workspace_id=workspace_a,
                    allowed_knowledge_base_ids=(101,),
                    limit=10,
                )
                == []
            )
        finally:
            if await client.collection_exists(collection):
                await client.delete_collection(collection_name=collection)
            await client.close()
            await engine.dispose()

    asyncio.run(exercise())
