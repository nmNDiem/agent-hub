from __future__ import annotations

import asyncio
import logging

from agent_hub_api.core.config import get_settings
from agent_hub_api.core.database import create_database_engine, create_session_factory
from agent_hub_api.operations.retention import RetentionSweeper
from agent_hub_api.widget.image_storage import SupabaseVisitorImageStorage

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is required to run the retention sweeper")
    storage = None
    if settings.supabase_url is not None and settings.supabase_service_role_key is not None:
        storage = SupabaseVisitorImageStorage(
            base_url=settings.supabase_url,
            service_key=settings.supabase_service_role_key,
            bucket=settings.storage_private_bucket,
        )
    engine = create_database_engine(settings.database_url)
    try:
        result = await RetentionSweeper(
            create_session_factory(engine), settings, storage
        ).run_once()
        logger.info(
            "retention_sweep_completed sessions_revoked=%s conversations_revoked=%s "
            "leads_deleted=%s grants_deleted=%s rate_windows_deleted=%s "
            "images_deleted=%s image_cleanup_failed=%s conversations_deleted=%s "
            "sessions_deleted=%s",
            result.sessions_revoked,
            result.conversations_revoked,
            result.leads_deleted,
            result.grants_deleted,
            result.rate_windows_deleted,
            result.images_deleted,
            result.image_cleanup_failed,
            result.conversations_deleted,
            result.sessions_deleted,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
