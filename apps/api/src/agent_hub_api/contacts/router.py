from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.contacts.schemas import (
    ContactDetailResponse,
    ContactListResponse,
    ContactMergeRequest,
    ContactNoteRequest,
    ContactStateRequest,
    ContactTagRequest,
)
from agent_hub_api.contacts.service import ContactService
from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user, require_csrf
from agent_hub_api.identity.models import User

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/contacts", tags=["contacts"])


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("", response_model=ContactListResponse)
async def list_contacts(
    workspace_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    query: Annotated[str | None, Query(max_length=120)] = None,
    assigned_member_id: Annotated[int | None, Query(ge=1)] = None,
    tag_id: Annotated[int | None, Query(ge=1)] = None,
) -> ContactListResponse:
    response.headers["Cache-Control"] = "no-store"
    return await ContactService(session, settings).list_contacts(
        user,
        workspace_id,
        limit=limit,
        cursor=cursor,
        query=query,
        assigned_member_id=assigned_member_id,
        tag_id=tag_id,
    )


@router.get("/export.csv")
async def export_contacts(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    content = await ContactService(session, settings).export_csv(user, workspace_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="agenthub-contacts.csv"',
        },
    )


@router.get("/{contact_public_id}", response_model=ContactDetailResponse)
async def get_contact(
    workspace_id: UUID,
    contact_public_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ContactDetailResponse:
    response.headers["Cache-Control"] = "no-store"
    return await ContactService(session, settings).detail(user, workspace_id, contact_public_id)


@router.patch(
    "/{contact_public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def update_contact(
    workspace_id: UUID,
    contact_public_id: UUID,
    payload: ContactStateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await ContactService(session, settings).update_state(
        user, workspace_id, contact_public_id, payload
    )


@router.post(
    "/{contact_public_id}/notes",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def add_contact_note(
    workspace_id: UUID,
    contact_public_id: UUID,
    payload: ContactNoteRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await ContactService(session, settings).add_note(user, workspace_id, contact_public_id, payload)


@router.post(
    "/{contact_public_id}/tags",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def add_contact_tag(
    workspace_id: UUID,
    contact_public_id: UUID,
    payload: ContactTagRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await ContactService(session, settings).add_tag(user, workspace_id, contact_public_id, payload)


@router.post(
    "/{target_contact_public_id}/merges",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def merge_contacts(
    workspace_id: UUID,
    target_contact_public_id: UUID,
    payload: ContactMergeRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, int]:
    merge_id = await ContactService(session, settings).merge(
        user, workspace_id, target_contact_public_id, payload
    )
    return {"merge_id": merge_id}


@router.post(
    "/{target_contact_public_id}/merges/{merge_id}/reverse",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def reverse_contact_merge(
    workspace_id: UUID,
    target_contact_public_id: UUID,
    merge_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await ContactService(session, settings).reverse_merge(
        user, workspace_id, target_contact_public_id, merge_id
    )
