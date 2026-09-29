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


class EmbeddingProvider(Protocol):
    async def embed(
        self, profile: EmbeddingProfileSpec, texts: list[str]
    ) -> list[tuple[float, ...]]: ...


class KnowledgeVectorIndex(Protocol):
    async def upsert(
        self, profile: EmbeddingProfileSpec, points: list[VectorPoint]
    ) -> None: ...

    async def delete(
        self, profile: EmbeddingProfileSpec, point_ids: list[UUID]
    ) -> None: ...


class ProviderTemporaryError(RuntimeError):
    """An external provider operation can be retried safely."""
