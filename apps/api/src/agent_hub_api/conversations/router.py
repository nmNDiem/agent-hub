from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.conversations.schemas import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationNoteRequest,
    ConversationStateRequest,
    ConversationTagRequest,
    DashboardResponse,
    HumanReplyRequest,
    InboxMemberListResponse,
)
from agent_hub_api.conversations.service import ConversationService
from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user, require_csrf
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
    channel: Literal["web", "facebook", "zalo"] | None = None,
    workflow_status: Literal["open", "pending", "resolved"] | None = None,
    assigned_member_id: int | None = None,
    tag_id: int | None = None,
) -> ConversationListResponse:
    response.headers["Cache-Control"] = "no-store"
    return await ConversationService(session, settings).list(
        user,
        workspace_id,
        limit=limit,
        cursor=cursor,
        days=cast(Literal[7, 30], int(days)) if days is not None else None,
        agent_public_id=agent_public_id,
        provider=channel,
        workflow_status=workflow_status,
        assigned_member_id=assigned_member_id,
        tag_id=tag_id,
    )


@router.get("/inbox/members", response_model=InboxMemberListResponse)
async def list_inbox_members(
    workspace_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InboxMemberListResponse:
    response.headers["Cache-Control"] = "no-store"
    return await ConversationService(session, settings).members(user, workspace_id)


@router.post(
    "/conversations/{conversation_public_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def mark_conversation_read(
    workspace_id: UUID,
    conversation_public_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await ConversationService(session, settings).mark_read(
        user, workspace_id, conversation_public_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/conversations/{conversation_public_id}/state",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def update_conversation_state(
    workspace_id: UUID,
    conversation_public_id: UUID,
    payload: ConversationStateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await ConversationService(session, settings).update_state(
        user, workspace_id, conversation_public_id, payload
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{conversation_public_id}/notes",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def add_conversation_note(
    workspace_id: UUID,
    conversation_public_id: UUID,
    payload: ConversationNoteRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await ConversationService(session, settings).add_note(
        user, workspace_id, conversation_public_id, payload
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{conversation_public_id}/tags",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def add_conversation_tag(
    workspace_id: UUID,
    conversation_public_id: UUID,
    payload: ConversationTagRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await ConversationService(session, settings).add_tag(
        user, workspace_id, conversation_public_id, payload
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{conversation_public_id}/replies",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def reply_to_conversation(
    workspace_id: UUID,
    conversation_public_id: UUID,
    payload: HumanReplyRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Response:
    key = (idempotency_key or "").strip()
    if not 8 <= len(key) <= 128:
        from agent_hub_api.core.errors import ApiError

        raise ApiError(
            status.HTTP_400_BAD_REQUEST, "INVALID_IDEMPOTENCY_KEY", "Khóa gửi tin không hợp lệ."
        )
    await ConversationService(session, settings).reply(
        user, workspace_id, conversation_public_id, key, payload
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
