from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.conversations.schemas import (
    ConversationDetailResponse,
    ConversationListResponse,
    DashboardResponse,
)
from agent_hub_api.conversations.service import ConversationService
from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user
from agent_hub_api.identity.models import User

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["conversations"])


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    workspace_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    days: Literal["7", "30"] | None = None,
    agent_public_id: UUID | None = None,
) -> ConversationListResponse:
    response.headers["Cache-Control"] = "no-store"
    return await ConversationService(session, settings).list(
        user,
        workspace_id,
        limit=limit,
        cursor=cursor,
        days=cast(Literal[7, 30], int(days)) if days is not None else None,
        agent_public_id=agent_public_id,
    )


@router.get("/conversations/{conversation_public_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    workspace_id: UUID,
    conversation_public_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationDetailResponse:
    response.headers["Cache-Control"] = "no-store"
    return await ConversationService(session, settings).detail(
        user, workspace_id, conversation_public_id
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    workspace_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    days: Literal["7", "30"] = "7",
) -> DashboardResponse:
    response.headers["Cache-Control"] = "no-store"
    return await ConversationService(session, settings).dashboard(
        user, workspace_id, cast(Literal[7, 30], int(days))
    )
