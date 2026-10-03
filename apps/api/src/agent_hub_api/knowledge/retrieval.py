from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent
from agent_hub_api.core.errors import ApiError
from agent_hub_api.knowledge.ingestion import profile_spec
from agent_hub_api.knowledge.models import (
    AgentKnowledgeBase,
    EmbeddingProfile,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeDocumentActiveGeneration,
    KnowledgeGeneration,
)
from agent_hub_api.knowledge.providers import (
    EmbeddingProvider,
    KnowledgeVectorIndex,
    ProviderPermanentError,
    ProviderTemporaryError,
    VectorSearchHit,
)


@dataclass(frozen=True, slots=True)
class AuthorizedKnowledgeScope:
    workspace_id: UUID
    allowed_knowledge_base_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    knowledge_base_id: int
    document_id: int
    document_title: str
    chunk_id: int
    source_locator: str


@dataclass(frozen=True, slots=True)
class RetrievedKnowledge:
    content: str
    citation: KnowledgeCitation
    embedding_profile_id: int
    similarity_score: float


class KnowledgeRetrievalUnavailable(RuntimeError):
    """Semantic retrieval cannot safely return scoped, authoritative results."""


async def resolve_agent_knowledge_scope(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    public_agent_id: UUID,
) -> AuthorizedKnowledgeScope:
    """Resolve immutable allowed sources after caller/session authorization."""

    agent = await session.scalar(
        select(Agent).where(
            Agent.workspace_id == workspace_id,
            Agent.public_id == public_agent_id,
            Agent.archived_at.is_(None),
        )
    )
    if agent is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Khong tim thay agent.")
    return await resolve_agent_knowledge_scope_for_agent(session, agent)


async def resolve_agent_knowledge_scope_for_agent(
    session: AsyncSession,
    agent: Agent,
) -> AuthorizedKnowledgeScope:
    """Resolve active knowledge assignments for an already scoped agent."""

    base_ids = tuple(
        await session.scalars(
            select(AgentKnowledgeBase.knowledge_base_id)
            .join(
                KnowledgeBase,
                and_(
                    KnowledgeBase.workspace_id == AgentKnowledgeBase.workspace_id,
                    KnowledgeBase.id == AgentKnowledgeBase.knowledge_base_id,
                ),
            )
            .where(
                AgentKnowledgeBase.workspace_id == agent.workspace_id,
                AgentKnowledgeBase.agent_id == agent.id,
                KnowledgeBase.status == "active",
            )
            .order_by(AgentKnowledgeBase.knowledge_base_id)
        )
    )
    return AuthorizedKnowledgeScope(agent.workspace_id, base_ids)


async def resolve_knowledge_scope_ids(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    knowledge_base_ids: tuple[int, ...],
) -> AuthorizedKnowledgeScope:
    """Revalidate a previously authorized immutable source set against active rows."""

    if not knowledge_base_ids:
        return AuthorizedKnowledgeScope(workspace_id, ())
    active_ids = tuple(
        await session.scalars(
            select(KnowledgeBase.id)
            .where(
                KnowledgeBase.workspace_id == workspace_id,
                KnowledgeBase.id.in_(knowledge_base_ids),
                KnowledgeBase.status == "active",
            )
            .order_by(KnowledgeBase.id)
        )
    )
    return AuthorizedKnowledgeScope(workspace_id, active_ids)


class KnowledgeRetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        embedding_provider: EmbeddingProvider,
        vector_index: KnowledgeVectorIndex,
    ) -> None:
        self.session = session
        self.embedding_provider = embedding_provider
        self.vector_index = vector_index

    async def search(
        self,
        scope: AuthorizedKnowledgeScope,
        query: str,
        *,
        limit: int = 5,
    ) -> list[RetrievedKnowledge]:
        normalized_query = query.strip()
        if not normalized_query or not scope.allowed_knowledge_base_ids or limit < 1:
            return []
        if limit > 20:
            raise ValueError("Knowledge retrieval limit cannot exceed 20")

        profile_rows = (
            await self.session.execute(
                select(KnowledgeBase.id, EmbeddingProfile)
                .join(
                    EmbeddingProfile,
                    EmbeddingProfile.id == KnowledgeBase.active_embedding_profile_id,
                )
                .where(
                    KnowledgeBase.workspace_id == scope.workspace_id,
                    KnowledgeBase.id.in_(scope.allowed_knowledge_base_ids),
                    KnowledgeBase.status == "active",
                    EmbeddingProfile.status == "active",
                )
                .order_by(EmbeddingProfile.id, KnowledgeBase.id)
            )
        ).all()
        bases_by_profile: dict[int, list[int]] = {}
        profiles: dict[int, EmbeddingProfile] = {}
        for base_id, profile in profile_rows:
            bases_by_profile.setdefault(profile.id, []).append(base_id)
            profiles[profile.id] = profile

        hits_by_profile: dict[int, list[VectorSearchHit]] = {}
        try:
            for profile_id in sorted(profiles):
                profile = profiles[profile_id]
                spec = profile_spec(profile)
                vectors = await self.embedding_provider.embed(spec, [normalized_query])
                if len(vectors) != 1 or len(vectors[0]) != spec.dimensions:
                    raise ProviderPermanentError(
                        "Embedding provider returned an invalid query vector"
                    )
                hits_by_profile[profile_id] = await self.vector_index.search(
                    spec,
                    vectors[0],
                    workspace_id=scope.workspace_id,
                    allowed_knowledge_base_ids=tuple(bases_by_profile[profile_id]),
                    limit=limit * 3,
                )
        except (ProviderPermanentError, ProviderTemporaryError) as exc:
            raise KnowledgeRetrievalUnavailable(
                "Knowledge retrieval provider is unavailable"
            ) from exc

        all_hits = [hit for hits in hits_by_profile.values() for hit in hits]
        valid = await self._revalidate(scope, all_hits)
        ordered: list[RetrievedKnowledge] = []
        max_rank = max((len(hits) for hits in hits_by_profile.values()), default=0)
        for rank in range(max_rank):
            for profile_id in sorted(hits_by_profile):
                hits = hits_by_profile[profile_id]
                if rank >= len(hits):
                    continue
                item = valid.get(hits[rank].point_id)
                if item is not None:
                    ordered.append(item)
                    if len(ordered) == limit:
                        return ordered
        return ordered

    async def _revalidate(
        self,
        scope: AuthorizedKnowledgeScope,
        hits: list[VectorSearchHit],
    ) -> dict[UUID, RetrievedKnowledge]:
        if not hits:
            return {}
        hit_by_id = {hit.point_id: hit for hit in hits}
        rows = (
            await self.session.execute(
                select(
                    KnowledgeChunkEmbedding,
                    KnowledgeChunk,
                    KnowledgeGeneration,
                    KnowledgeDocument,
                    KnowledgeBase,
                )
                .join(
                    KnowledgeChunk,
                    and_(
                        KnowledgeChunk.workspace_id == KnowledgeChunkEmbedding.workspace_id,
                        KnowledgeChunk.id == KnowledgeChunkEmbedding.chunk_id,
                    ),
                )
                .join(
                    KnowledgeGeneration,
                    and_(
                        KnowledgeGeneration.workspace_id == KnowledgeChunk.workspace_id,
                        KnowledgeGeneration.id == KnowledgeChunk.generation_id,
                    ),
                )
                .join(
                    KnowledgeDocumentActiveGeneration,
                    and_(
                        KnowledgeDocumentActiveGeneration.workspace_id
                        == KnowledgeGeneration.workspace_id,
                        KnowledgeDocumentActiveGeneration.document_id
                        == KnowledgeGeneration.document_id,
                        KnowledgeDocumentActiveGeneration.generation_id
                        == KnowledgeGeneration.id,
                    ),
                )
                .join(
                    KnowledgeDocument,
                    and_(
                        KnowledgeDocument.workspace_id == KnowledgeGeneration.workspace_id,
                        KnowledgeDocument.id == KnowledgeGeneration.document_id,
                    ),
                )
                .join(
                    KnowledgeBase,
                    and_(
                        KnowledgeBase.workspace_id == KnowledgeDocument.workspace_id,
                        KnowledgeBase.id == KnowledgeDocument.knowledge_base_id,
                    ),
                )
                .where(
                    KnowledgeChunkEmbedding.workspace_id == scope.workspace_id,
                    KnowledgeChunkEmbedding.qdrant_point_id.in_(hit_by_id),
                    KnowledgeChunkEmbedding.status == "indexed",
                    KnowledgeChunkEmbedding.content_hash == KnowledgeChunk.content_sha256,
                    KnowledgeGeneration.status == "ready",
                    KnowledgeDocument.status == "active",
                    KnowledgeBase.status == "active",
                    KnowledgeBase.id.in_(scope.allowed_knowledge_base_ids),
                    KnowledgeBase.active_embedding_profile_id
                    == KnowledgeChunkEmbedding.embedding_profile_id,
                    KnowledgeGeneration.embedding_profile_id
                    == KnowledgeChunkEmbedding.embedding_profile_id,
                )
            )
        ).all()

        valid: dict[UUID, RetrievedKnowledge] = {}
        for mapping, chunk, generation, document, knowledge_base in rows:
            hit = hit_by_id.get(mapping.qdrant_point_id)
            if hit is None or not self._payload_matches(
                hit,
                scope=scope,
                mapping=mapping,
                chunk=chunk,
                generation=generation,
                document=document,
                knowledge_base=knowledge_base,
            ):
                continue
            valid[mapping.qdrant_point_id] = RetrievedKnowledge(
                content=chunk.content,
                citation=KnowledgeCitation(
                    knowledge_base_id=knowledge_base.id,
                    document_id=document.id,
                    document_title=document.title,
                    chunk_id=chunk.id,
                    source_locator=chunk.source_locator,
                ),
                embedding_profile_id=mapping.embedding_profile_id,
                similarity_score=hit.score,
            )
        return valid

    @staticmethod
    def _payload_matches(
        hit: VectorSearchHit,
        *,
        scope: AuthorizedKnowledgeScope,
        mapping: KnowledgeChunkEmbedding,
        chunk: KnowledgeChunk,
        generation: KnowledgeGeneration,
        document: KnowledgeDocument,
        knowledge_base: KnowledgeBase,
    ) -> bool:
        expected: dict[str, str | int] = {
            "workspace_id": str(scope.workspace_id),
            "knowledge_base_id": knowledge_base.id,
            "document_id": document.id,
            "document_version_id": generation.document_version_id,
            "generation_id": generation.id,
            "generation": generation.generation_no,
            "chunk_id": chunk.id,
            "embedding_profile_id": mapping.embedding_profile_id,
            "content_hash": chunk.content_sha256,
        }
        return all(hit.payload.get(key) == value for key, value in expected.items())
