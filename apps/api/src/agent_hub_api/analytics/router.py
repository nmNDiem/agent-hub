from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.analytics.schemas import OperationalAnalyticsResponse
from agent_hub_api.analytics.service import AnalyticsService, Channel
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user
from agent_hub_api.identity.models import User

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["analytics"])


@router.get("/analytics", response_model=OperationalAnalyticsResponse)
async def get_operational_analytics(
    workspace_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    days: Literal["7", "30"] = "7",
    channel: Annotated[Literal["web", "facebook", "zalo"] | None, Query()] = None,
    agent_public_id: UUID | None = None,
) -> OperationalAnalyticsResponse:
    response.headers["Cache-Control"] = "no-store"
    return await AnalyticsService(session).report(
        user,
        workspace_id,
        days=cast(Literal[7, 30], int(days)),
        channel=cast(Channel | None, channel),
        agent_public_id=agent_public_id,
    )
