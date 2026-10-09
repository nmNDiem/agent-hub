from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from agent_hub_api.core.config import get_settings
from agent_hub_api.core.database import create_database_engine, create_session_factory
from agent_hub_api.knowledge.ingestion import KnowledgeIngestionWorker
from agent_hub_api.knowledge.reconcile import KnowledgeReconciler
from agent_hub_api.knowledge.runner import run_worker_process
from agent_hub_api.knowledge.runtime import (
    create_openai_embedding_provider,
    create_qdrant_index,
)
from agent_hub_api.knowledge.storage import SupabaseKnowledgeStorage


async def main() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is required to run the knowledge worker")
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        raise ValueError("Supabase Storage credentials are required to run the knowledge worker")

    engine = create_database_engine(settings)
    sessions = create_session_factory(engine)
    vector_index = create_qdrant_index(settings)
    storage = SupabaseKnowledgeStorage(
        base_url=settings.supabase_url,
        service_key=settings.supabase_service_role_key,
        bucket=settings.storage_private_bucket,
    )
    worker = KnowledgeIngestionWorker(
        session_factory=sessions,
        settings=settings,
        storage=storage,
        embedding_provider=create_openai_embedding_provider(settings),
        vector_index=vector_index,
    )
    reconciler = KnowledgeReconciler(
        session_factory=sessions,
        settings=settings,
        storage=storage,
        vector_index=vector_index,
    )
    stop = asyncio.Event()
    try:
        await run_worker_process(
            worker,
            reconciler,
            stop=stop,
            poll_seconds=settings.knowledge_worker_poll_seconds,
        )
    finally:
        await vector_index.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
