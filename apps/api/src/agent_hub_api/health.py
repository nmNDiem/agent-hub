import logging
from typing import Literal, cast

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.core.config import Settings

router = APIRouter(tags=["operations"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    service: str
    environment: str
    database: Literal["ok"]


def _liveness(request: Request) -> HealthResponse:
    settings = cast(Settings, request.app.state.settings)
    return HealthResponse(status="ok", service=settings.app_name, environment=settings.app_env)


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return _liveness(request)


@router.get("/health/live", response_model=HealthResponse)
async def liveness(request: Request) -> HealthResponse:
    return _liveness(request)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service is not ready"}},
)
async def readiness(request: Request) -> ReadinessResponse | JSONResponse:
    settings = cast(Settings, request.app.state.settings)
    session_factory = cast(
        async_sessionmaker[AsyncSession] | None,
        getattr(request.app.state, "session_factory", None),
    )
    if session_factory is None:
        return _not_ready(request, settings, "database_unconfigured")
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return _not_ready(request, settings, "database_unavailable")
    return ReadinessResponse(
        status="ready",
        service=settings.app_name,
        environment=settings.app_env,
        database="ok",
    )


def _not_ready(request: Request, settings: Settings, reason: str) -> JSONResponse:
    logger.warning(
        "readiness_check_failed request_id=%s reason=%s",
        getattr(request.state, "request_id", "unknown"),
        reason,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "not_ready",
            "service": settings.app_name,
            "environment": settings.app_env,
            "database": "unavailable",
        },
    )
