from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.schemas import (
    AgentCatalogScopeRequest,
    AgentCreateRequest,
    AgentListResponse,
    AgentResponse,
    AgentUpdateRequest,
)
from agent_hub_api.agents.service import AgentService
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user, require_csrf
from agent_hub_api.identity.models import User

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/agents", tags=["agents"])


def service(session: AsyncSession) -> AgentService:
    return AgentService(session)


@router.get("", response_model=AgentListResponse)
async def list_agents(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentListResponse:
    return await service(session).list(user, workspace_id)


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_agent(
    workspace_id: UUID,
    payload: AgentCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    return await service(session).create(user, workspace_id, payload)


@router.get("/{public_agent_id}", response_model=AgentResponse)
async def get_agent(
    workspace_id: UUID,
    public_agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    return await service(session).get(user, workspace_id, public_agent_id)


@router.patch(
    "/{public_agent_id}",
    response_model=AgentResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_agent(
    workspace_id: UUID,
    public_agent_id: UUID,
    payload: AgentUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    return await service(session).update(user, workspace_id, public_agent_id, payload)


@router.put(
    "/{public_agent_id}/catalog-scope",
    response_model=AgentResponse,
    dependencies=[Depends(require_csrf)],
)
async def replace_agent_catalog_scope(
    workspace_id: UUID,
    public_agent_id: UUID,
    payload: AgentCatalogScopeRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    return await service(session).replace_catalog_scope(
        user, workspace_id, public_agent_id, payload
    )
