from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user
from agent_hub_api.identity.models import User
from agent_hub_api.telemetry.schemas import UsageSummaryResponse
from agent_hub_api.telemetry.service import TelemetryService

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["telemetry"])


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage(
    workspace_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsageSummaryResponse:
    response.headers["Cache-Control"] = "no-store"
    return await TelemetryService(session, settings).summary(user, workspace_id)
