from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user, require_csrf
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.schemas import (
    CreateWorkspaceRequest,
    MeResponse,
    UpdateWorkspaceRequest,
    WorkspaceResponse,
)
from agent_hub_api.workspaces.service import WorkspaceService, workspace_response

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])
profile_router = APIRouter(prefix="/api/v1", tags=["authentication"])


@profile_router.get("/me", response_model=MeResponse)
async def me(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeResponse:
    return await WorkspaceService(session).me(user)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[WorkspaceResponse]:
    return await WorkspaceService(session).list_for_user(user.id)


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponse:
    return await WorkspaceService(session).create(user, payload)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponse:
    workspace, role = await WorkspaceService(session).get_for_user(user.id, workspace_id)
    return workspace_response(workspace, role)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_workspace(
    workspace_id: UUID,
    payload: UpdateWorkspaceRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceResponse:
    return await WorkspaceService(session).update(user, workspace_id, payload)
