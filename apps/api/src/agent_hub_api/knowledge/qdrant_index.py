from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from agent_hub_api.knowledge.providers import (
    EmbeddingProfileSpec,
    ProviderPermanentError,
    ProviderTemporaryError,
    VectorPoint,
    VectorSearchHit,
)


def _distance(metric: str) -> models.Distance:
    values = {
        "cosine": models.Distance.COSINE,
        "dot": models.Distance.DOT,
        "euclid": models.Distance.EUCLID,
    }
    try:
        return values[metric]
    except KeyError as exc:
        raise ProviderPermanentError("Unsupported Qdrant distance metric") from exc


async def _qdrant_call[T](operation: Callable[[], Awaitable[T]]) -> T:
    try:
        return await operation()
    except UnexpectedResponse as exc:
        if exc.status_code == 429 or (exc.status_code is not None and exc.status_code >= 500):
            raise ProviderTemporaryError("Qdrant is temporarily unavailable") from exc
        raise ProviderPermanentError("Qdrant rejected the request") from exc
    except (ResponseHandlingException, TimeoutError, OSError) as exc:
        raise ProviderTemporaryError("Qdrant is temporarily unavailable") from exc


class QdrantKnowledgeVectorIndex:
    """Tenant-filtered Qdrant adapter; PostgreSQL remains authoritative."""

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int = 30,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        if client is None and not url:
            raise ValueError("QDRANT_URL is required for the Qdrant vector index")
        self._client = client or AsyncQdrantClient(
            url=url,
            api_key=api_key,
            timeout=timeout_seconds,
            prefer_grpc=False,
        )

    async def ensure_profile(self, profile: EmbeddingProfileSpec) -> None:
        exists = await _qdrant_call(
            lambda: self._client.collection_exists(profile.collection)
        )
        if not exists:
            try:
                await _qdrant_call(
                    lambda: self._client.create_collection(
                        collection_name=profile.collection,
                        vectors_config=models.VectorParams(
                            size=profile.dimensions,
                            distance=_distance(profile.distance_metric),
                        ),
                    )
                )
            except ProviderPermanentError:
                # A concurrent bootstrap may have created the collection after the check.
                if not await _qdrant_call(
                    lambda: self._client.collection_exists(profile.collection)
                ):
                    raise

        info = await _qdrant_call(lambda: self._client.get_collection(profile.collection))
        vectors = info.config.params.vectors
        if not isinstance(vectors, models.VectorParams):
            raise ProviderPermanentError("Qdrant profile collection must use one unnamed vector")
        if vectors.size != profile.dimensions or vectors.distance != _distance(
            profile.distance_metric
        ):
            raise ProviderPermanentError("Qdrant collection does not match embedding profile")

        await self._ensure_payload_index(
            profile.collection,
            "workspace_id",
            models.KeywordIndexParams(
                type=models.KeywordIndexType.KEYWORD,
                is_tenant=True,
            ),
        )
        for field_name in ("knowledge_base_id", "embedding_profile_id"):
            await self._ensure_payload_index(
                profile.collection,
                field_name,
                models.PayloadSchemaType.INTEGER,
            )

    async def _ensure_payload_index(
        self,
        collection: str,
        field_name: str,
        schema: models.PayloadSchemaType | models.KeywordIndexParams,
    ) -> None:
        try:
            await _qdrant_call(
                lambda: self._client.create_payload_index(
                    collection_name=collection,
                    field_name=field_name,
                    field_schema=schema,
                    wait=True,
                )
            )
        except ProviderPermanentError:
            info = await _qdrant_call(lambda: self._client.get_collection(collection))
            if field_name not in info.payload_schema:
                raise

    async def upsert(
        self, profile: EmbeddingProfileSpec, points: list[VectorPoint]
    ) -> None:
        if not points:
            return
        if any(len(point.vector) != profile.dimensions for point in points):
            raise ProviderPermanentError("Vector dimension does not match embedding profile")
        await _qdrant_call(
            lambda: self._client.upsert(
                collection_name=profile.collection,
                points=[
                    models.PointStruct(
                        id=point.point_id,
                        vector=list(point.vector),
                        payload=point.payload,
                    )
                    for point in points
                ],
                wait=True,
            )
        )

    async def search(
        self,
        profile: EmbeddingProfileSpec,
        vector: tuple[float, ...],
        *,
        workspace_id: UUID,
        allowed_knowledge_base_ids: tuple[int, ...],
        limit: int,
    ) -> list[VectorSearchHit]:
        if not allowed_knowledge_base_ids or limit < 1:
            return []
        if len(vector) != profile.dimensions:
            raise ProviderPermanentError("Query vector dimension does not match profile")
        response = await _qdrant_call(
            lambda: self._client.query_points(
                collection_name=profile.collection,
                query=list(vector),
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="workspace_id",
                            match=models.MatchValue(value=str(workspace_id)),
                        ),
                        models.FieldCondition(
                            key="knowledge_base_id",
                            match=models.MatchAny(any=list(allowed_knowledge_base_ids)),
                        ),
                        models.FieldCondition(
                            key="embedding_profile_id",
                            match=models.MatchValue(value=profile.id),
                        ),
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        )
        hits: list[VectorSearchHit] = []
        for point in response.points:
            try:
                point_id = point.id if isinstance(point.id, UUID) else UUID(str(point.id))
            except ValueError as exc:
                raise ProviderPermanentError("Qdrant returned an invalid point identifier") from exc
            payload = {
                key: value
                for key, value in (point.payload or {}).items()
                if isinstance(value, str | int) and not isinstance(value, bool)
            }
            hits.append(
                VectorSearchHit(
                    point_id=point_id,
                    score=float(point.score),
                    payload=payload,
                )
            )
        return hits

    async def delete(
        self, profile: EmbeddingProfileSpec, point_ids: list[UUID]
    ) -> None:
        if not point_ids:
            return
        await _qdrant_call(
            lambda: self._client.delete(
                collection_name=profile.collection,
                points_selector=models.PointIdsList(
                    points=cast(list[int | str | UUID], point_ids)
                ),
                wait=True,
            )
        )

    async def close(self) -> None:
        await self._client.close()
