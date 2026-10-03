from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user, require_csrf
from agent_hub_api.identity.models import User
from agent_hub_api.widget.schemas import WidgetConfigRequest, WidgetConfigResponse
from agent_hub_api.widget.service import WidgetAdminService

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/agents", tags=["widget-admin"])


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def service(session: AsyncSession, settings: Settings) -> WidgetAdminService:
    return WidgetAdminService(session, settings)


@router.get("/{public_agent_id}/widget", response_model=WidgetConfigResponse)
async def get_widget_config(
    workspace_id: UUID,
    public_agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WidgetConfigResponse:
    return await service(session, settings).get(user, workspace_id, public_agent_id)


@router.put(
    "/{public_agent_id}/widget",
    response_model=WidgetConfigResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_widget_config(
    workspace_id: UUID,
    public_agent_id: UUID,
    payload: WidgetConfigRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WidgetConfigResponse:
    return await service(session, settings).update(user, workspace_id, public_agent_id, payload)


@router.post(
    "/{public_agent_id}/publish",
    response_model=WidgetConfigResponse,
    dependencies=[Depends(require_csrf)],
)
async def publish_widget(
    workspace_id: UUID,
    public_agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WidgetConfigResponse:
    return await service(session, settings).publish(user, workspace_id, public_agent_id)


@router.post(
    "/{public_agent_id}/pause",
    response_model=WidgetConfigResponse,
    dependencies=[Depends(require_csrf)],
)
async def pause_widget(
    workspace_id: UUID,
    public_agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WidgetConfigResponse:
    return await service(session, settings).pause(user, workspace_id, public_agent_id)
