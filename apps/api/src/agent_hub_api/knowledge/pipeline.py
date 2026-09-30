from __future__ import annotations

import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeGeneration,
)

CHUNKER_VERSION = "char-paragraph-v1"


def pipeline_config_hash(profile_id: int, settings: Settings) -> str:
    payload = json.dumps(
        {
            "profile_id": profile_id,
            "chunker_version": CHUNKER_VERSION,
            "chunk_size": settings.knowledge_chunk_size,
            "chunk_overlap": settings.knowledge_chunk_overlap,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def create_generation(
    session: AsyncSession,
    *,
    document: KnowledgeDocument,
    version: KnowledgeDocumentVersion,
    embedding_profile_id: int,
    settings: Settings,
) -> KnowledgeGeneration:
    generation_no = int(
        await session.scalar(
            select(func.max(KnowledgeGeneration.generation_no)).where(
                KnowledgeGeneration.document_id == document.id
            )
        )
        or 0
    ) + 1
    generation = KnowledgeGeneration(
        workspace_id=document.workspace_id,
        document_id=document.id,
        document_version_id=version.id,
        embedding_profile_id=embedding_profile_id,
        generation_no=generation_no,
        chunker_version=CHUNKER_VERSION,
        chunk_size=settings.knowledge_chunk_size,
        chunk_overlap=settings.knowledge_chunk_overlap,
        pipeline_config_hash=pipeline_config_hash(embedding_profile_id, settings),
    )
    session.add(generation)
    await session.flush()
    return generation
