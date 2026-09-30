from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EmbeddingProfileSpec:
    id: int
    provider: str
    model: str
    dimensions: int
    provider_model_revision: str | None
    pipeline_version: str
    distance_metric: str
    collection: str
    config_hash: str


@dataclass(frozen=True, slots=True)
class VectorPoint:
    point_id: UUID
    vector: tuple[float, ...]
    payload: dict[str, str | int]


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    point_id: UUID
    score: float
    payload: dict[str, str | int]


class EmbeddingProvider(Protocol):
    async def embed(
        self, profile: EmbeddingProfileSpec, texts: list[str]
    ) -> list[tuple[float, ...]]: ...


class KnowledgeVectorIndex(Protocol):
    async def ensure_profile(self, profile: EmbeddingProfileSpec) -> None: ...

    async def upsert(
        self, profile: EmbeddingProfileSpec, points: list[VectorPoint]
    ) -> None: ...

    async def search(
        self,
        profile: EmbeddingProfileSpec,
        vector: tuple[float, ...],
        *,
        workspace_id: UUID,
        allowed_knowledge_base_ids: tuple[int, ...],
        limit: int,
    ) -> list[VectorSearchHit]: ...

    async def delete(
        self, profile: EmbeddingProfileSpec, point_ids: list[UUID]
    ) -> None: ...


class ProviderTemporaryError(RuntimeError):
    """An external provider operation can be retried safely."""


class ProviderPermanentError(RuntimeError):
    """An external provider rejected configuration or input permanently."""
