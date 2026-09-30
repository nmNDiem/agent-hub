from __future__ import annotations

from agent_hub_api.core.config import Settings
from agent_hub_api.knowledge.openai_embeddings import OpenAIEmbeddingProvider
from agent_hub_api.knowledge.qdrant_index import QdrantKnowledgeVectorIndex


def create_qdrant_index(settings: Settings) -> QdrantKnowledgeVectorIndex:
    if settings.qdrant_url is None:
        raise ValueError("QDRANT_URL is required")
    return QdrantKnowledgeVectorIndex(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout_seconds=settings.qdrant_timeout_seconds,
    )


def create_openai_embedding_provider(settings: Settings) -> OpenAIEmbeddingProvider:
    if settings.openai_api_key is None:
        raise ValueError("OPENAI_API_KEY is required to run knowledge ingestion")
    return OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key,
        timeout_seconds=settings.openai_timeout_seconds,
    )
