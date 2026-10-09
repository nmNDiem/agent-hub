from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.openai_generation import create_openai_generation_gateway
from agent_hub_api.agents.runtime import AgentRuntimeBudget, AgentRuntimeService
from agent_hub_api.channels.service import ChannelService, DeliveryRunner
from agent_hub_api.channels.vault import SupabaseCredentialVault
from agent_hub_api.core.config import get_settings
from agent_hub_api.core.database import create_database_engine, create_session_factory
from agent_hub_api.facebook.graph import HttpFacebookGraphGateway
from agent_hub_api.facebook.media import FacebookMediaDownloader, FacebookMediaLimits
from agent_hub_api.facebook.outbound import FacebookOutboundAdapter
from agent_hub_api.facebook.responses import FacebookResponseRunner, FacebookResponseService
from agent_hub_api.knowledge.runtime import (
    create_openai_embedding_provider,
    create_qdrant_index,
)
from agent_hub_api.widget.image_storage import SupabaseVisitorImageStorage
from agent_hub_api.widget.vision import create_openai_vision_gateway

logger = logging.getLogger("agent_hub_api.channel_worker")


async def main() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is required to run the channel worker")
    if settings.facebook_graph_api_version is None:
        raise ValueError("FACEBOOK_GRAPH_API_VERSION is required to run the channel worker")
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        raise ValueError("Supabase private Storage is required to run the channel worker")
    if not all(
        (
            settings.openai_api_key,
            settings.generation_model,
            settings.vision_model,
            settings.qdrant_url,
            settings.embedding_model,
            settings.embedding_dimensions,
        )
    ):
        raise ValueError("Grounded generation, vision and retrieval must be configured")

    engine = create_database_engine(settings.database_url)
    sessions = create_session_factory(engine)
    vault = SupabaseCredentialVault(sessions)
    graph = HttpFacebookGraphGateway(
        api_version=settings.facebook_graph_api_version,
        timeout_seconds=settings.facebook_graph_timeout_seconds,
        app_id=settings.facebook_app_id,
        app_secret=settings.facebook_app_secret,
    )
    adapter = FacebookOutboundAdapter(vault=vault, graph=graph)
    generation = create_openai_generation_gateway(settings)
    embedding = create_openai_embedding_provider(settings)
    vector_index = create_qdrant_index(settings)
    vision = create_openai_vision_gateway(settings)
    storage = SupabaseVisitorImageStorage(
        base_url=settings.supabase_url,
        service_key=settings.supabase_service_role_key,
        bucket=settings.storage_private_bucket,
    )

    def runtime_factory(session: AsyncSession) -> AgentRuntimeService:
        return AgentRuntimeService(
            session,
            gateway=generation,
            embedding_provider=embedding,
            vector_index=vector_index,
            budget=AgentRuntimeBudget.from_settings(settings),
        )

    media_downloader = FacebookMediaDownloader(
        FacebookMediaLimits(
            max_bytes=settings.facebook_media_max_bytes,
            max_pixels=settings.facebook_media_max_pixels,
            max_redirects=settings.facebook_media_max_redirects,
            timeout_seconds=settings.facebook_media_timeout_seconds,
            allowed_hosts=settings.facebook_media_allowed_hosts,
        )
    )
    try:
        while True:
            try:
                async with sessions() as session:
                    response_service = FacebookResponseService(session, settings)
                    worked = await FacebookResponseRunner(
                        response_service,
                        runtime_factory=runtime_factory,
                        media_downloader=media_downloader,
                        storage=storage,
                        vision=vision,
                    ).run_once()
                    if not worked:
                        worked = await DeliveryRunner(
                            ChannelService(
                                session,
                                response_window_hours=settings.facebook_response_window_hours,
                                response_job_max_attempts=settings.facebook_response_job_max_attempts,
                            ),
                            {"facebook": adapter},
                        ).run_once()
                    if not worked:
                        worked = await response_service.cleanup_once(storage)
            except Exception as exc:
                logger.error(
                    "channel_delivery_iteration_failed error_type=%s",
                    type(exc).__name__,
                )
                worked = False
            if not worked:
                await asyncio.sleep(settings.channel_worker_poll_seconds)
    finally:
        await generation.close()
        await embedding.close()
        await vector_index.close()
        await vision.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
