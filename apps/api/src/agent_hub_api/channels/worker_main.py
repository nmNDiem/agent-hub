from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from agent_hub_api.channels.service import ChannelService, DeliveryRunner
from agent_hub_api.channels.vault import SupabaseCredentialVault
from agent_hub_api.core.config import get_settings
from agent_hub_api.core.database import create_database_engine, create_session_factory
from agent_hub_api.facebook.graph import HttpFacebookGraphGateway
from agent_hub_api.facebook.outbound import FacebookOutboundAdapter

logger = logging.getLogger("agent_hub_api.channel_worker")


async def main() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is required to run the channel worker")
    if settings.facebook_graph_api_version is None:
        raise ValueError("FACEBOOK_GRAPH_API_VERSION is required to run the channel worker")

    engine = create_database_engine(settings.database_url)
    sessions = create_session_factory(engine)
    vault = SupabaseCredentialVault(sessions)
    graph = HttpFacebookGraphGateway(
        api_version=settings.facebook_graph_api_version,
        timeout_seconds=settings.facebook_graph_timeout_seconds,
    )
    adapter = FacebookOutboundAdapter(vault=vault, graph=graph)
    try:
        while True:
            try:
                async with sessions() as session:
                    worked = await DeliveryRunner(
                        ChannelService(session), {"facebook": adapter}
                    ).run_once()
            except Exception as exc:
                logger.error(
                    "channel_delivery_iteration_failed error_type=%s",
                    type(exc).__name__,
                )
                worked = False
            if not worked:
                await asyncio.sleep(settings.channel_worker_poll_seconds)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
