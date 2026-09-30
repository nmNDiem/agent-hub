import asyncio
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from agent_hub_api.knowledge.openai_embeddings import OpenAIEmbeddingProvider
from agent_hub_api.knowledge.providers import (
    EmbeddingProfileSpec,
    ProviderPermanentError,
    VectorPoint,
)
from agent_hub_api.knowledge.qdrant_index import QdrantKnowledgeVectorIndex


def profile(*, dimensions: int = 3) -> EmbeddingProfileSpec:
    return EmbeddingProfileSpec(
        id=7,
        provider="openai",
        model="test-embedding-model",
        dimensions=dimensions,
        provider_model_revision=None,
        pipeline_version="test-v1",
        distance_metric="cosine",
        collection="agenthub_test_profile",
        config_hash="a" * 64,
    )


@dataclass
class FakeEmbeddingRow:
    index: int
    embedding: list[float]


@dataclass
class FakeEmbeddingResponse:
    data: list[FakeEmbeddingRow]


class FakeEmbeddingsResource:
    def __init__(self, response: FakeEmbeddingResponse) -> None:
        self.response = response
        self.kwargs: dict[str, object] = {}

    async def create(self, **kwargs: object) -> FakeEmbeddingResponse:
        self.kwargs = kwargs
        return self.response


class FakeOpenAIClient:
    def __init__(self, response: FakeEmbeddingResponse) -> None:
        self.embeddings = FakeEmbeddingsResource(response)


def test_openai_embedding_adapter_batches_and_enforces_profile_dimensions() -> None:
    async def exercise() -> None:
        client = FakeOpenAIClient(
            FakeEmbeddingResponse(
                data=[
                    FakeEmbeddingRow(index=1, embedding=[4.0, 5.0, 6.0]),
                    FakeEmbeddingRow(index=0, embedding=[1.0, 2.0, 3.0]),
                ]
            )
        )
        provider = OpenAIEmbeddingProvider(client=cast(AsyncOpenAI, client))
        vectors = await provider.embed(profile(), ["first", "second"])
        assert vectors == [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        assert client.embeddings.kwargs == {
            "model": "test-embedding-model",
            "input": ["first", "second"],
            "dimensions": 3,
            "encoding_format": "float",
        }

        client.embeddings.response = FakeEmbeddingResponse(
            data=[FakeEmbeddingRow(index=0, embedding=[1.0, 2.0])]
        )
        with pytest.raises(ProviderPermanentError):
            await provider.embed(profile(), ["invalid dimension"])

    asyncio.run(exercise())


@dataclass
class FakeScoredPoint:
    id: UUID
    score: float
    payload: dict[str, str | int]


@dataclass
class FakeQueryResponse:
    points: list[FakeScoredPoint]


class FakeQdrantClient:
    def __init__(self) -> None:
        self.exists = False
        self.points: dict[UUID, models.PointStruct] = {}
        self.payload_indexes: set[str] = set()
        self.last_filter: models.Filter | None = None
        self.vector_params = models.VectorParams(size=3, distance=models.Distance.COSINE)

    async def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    async def create_collection(
        self, collection_name: str, vectors_config: models.VectorParams
    ) -> bool:
        self.exists = True
        self.vector_params = vectors_config
        return True

    async def get_collection(self, collection_name: str) -> Any:
        class Params:
            vectors = self.vector_params

        class Config:
            params = Params()

        class Info:
            config = Config()
            payload_schema = {name: object() for name in self.payload_indexes}

        return Info()

    async def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_schema: object,
        wait: bool,
    ) -> object:
        self.payload_indexes.add(field_name)
        return object()

    async def upsert(
        self, collection_name: str, points: list[models.PointStruct], wait: bool
    ) -> object:
        for point in points:
            assert isinstance(point.id, UUID)
            self.points[point.id] = point
        return object()

    async def query_points(self, **kwargs: object) -> FakeQueryResponse:
        self.last_filter = cast(models.Filter, kwargs["query_filter"])
        first = next(iter(self.points.values()))
        assert isinstance(first.id, UUID)
        return FakeQueryResponse(
            points=[
                FakeScoredPoint(
                    id=first.id,
                    score=0.9,
                    payload=cast(dict[str, str | int], first.payload),
                )
            ]
        )

    async def delete(
        self, collection_name: str, points_selector: models.PointIdsList, wait: bool
    ) -> object:
        for point_id in points_selector.points:
            self.points.pop(UUID(str(point_id)), None)
        return object()

    async def close(self) -> None:
        pass


def test_qdrant_adapter_creates_indexes_and_injects_tenant_source_filters() -> None:
    async def exercise() -> None:
        client = FakeQdrantClient()
        index = QdrantKnowledgeVectorIndex(client=cast(AsyncQdrantClient, client))
        spec = profile()
        await index.ensure_profile(spec)
        assert client.payload_indexes == {
            "workspace_id",
            "knowledge_base_id",
            "embedding_profile_id",
        }

        point_id = uuid4()
        workspace_id = uuid4()
        await index.upsert(
            spec,
            [
                VectorPoint(
                    point_id=point_id,
                    vector=(1.0, 0.0, 0.0),
                    payload={
                        "workspace_id": str(workspace_id),
                        "knowledge_base_id": 11,
                        "embedding_profile_id": spec.id,
                    },
                )
            ],
        )
        hits = await index.search(
            spec,
            (1.0, 0.0, 0.0),
            workspace_id=workspace_id,
            allowed_knowledge_base_ids=(11, 12),
            limit=5,
        )
        assert [hit.point_id for hit in hits] == [point_id]
        assert client.last_filter is not None
        conditions = cast(list[models.FieldCondition], client.last_filter.must)
        assert [condition.key for condition in conditions] == [
            "workspace_id",
            "knowledge_base_id",
            "embedding_profile_id",
        ]

        await index.delete(spec, [point_id])
        assert client.points == {}

    asyncio.run(exercise())
