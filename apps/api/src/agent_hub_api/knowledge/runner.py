from __future__ import annotations

import asyncio
from contextlib import suppress

from agent_hub_api.knowledge.ingestion import KnowledgeIngestionWorker
from agent_hub_api.knowledge.reconcile import KnowledgeReconciler


async def run_worker_process(
    worker: KnowledgeIngestionWorker,
    reconciler: KnowledgeReconciler,
    *,
    stop: asyncio.Event,
    poll_seconds: int,
) -> None:
    """Run the durable worker in a process separate from the FastAPI server."""

    while not stop.is_set():
        processed = await worker.run_once()
        if not processed:
            processed = await reconciler.run_once()
        if not processed:
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
