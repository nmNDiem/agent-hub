from fastapi import FastAPI

from agent_hub_api.config import get_settings
from agent_hub_api.health import router as health_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.0.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )
    application.include_router(health_router)
    return application


app = create_app()
