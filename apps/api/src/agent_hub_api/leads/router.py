from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user, require_csrf
from agent_hub_api.identity.models import User
from agent_hub_api.leads.schemas import (
    LeadDetailResponse,
    LeadListResponse,
    LeadQualificationRequest,
    LeadResponse,
    LeadStatus,
    LeadStatusRequest,
)
from agent_hub_api.leads.service import LeadService

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/leads", tags=["leads"])


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("", response_model=LeadListResponse)
async def list_leads(
    workspace_id: UUID,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    followup_status: LeadStatus | None = None,
) -> LeadListResponse:
    response.headers["Cache-Control"] = "no-store"
    return await LeadService(session, settings).list(
        user,
        workspace_id,
        limit=limit,
        cursor=cursor,
        followup_status=followup_status,
    )


@router.get("/export.csv")
async def export_leads(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    followup_status: LeadStatus | None = None,
) -> Response:
    content = await LeadService(session, settings).export_csv(
        user, workspace_id, followup_status=followup_status
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="agenthub-leads.csv"',
        },
    )


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    workspace_id: UUID,
    lead_id: int,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LeadDetailResponse:
    response.headers["Cache-Control"] = "no-store"
    return await LeadService(session, settings).detail(user, workspace_id, lead_id)


@router.patch(
    "/{lead_id}/qualification",
    response_model=LeadResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_lead_qualification(
    workspace_id: UUID,
    lead_id: int,
    payload: LeadQualificationRequest,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LeadResponse:
    response.headers["Cache-Control"] = "no-store"
    return await LeadService(session, settings).update_qualification(
        user, workspace_id, lead_id, payload
    )


@router.patch(
    "/{lead_id}",
    response_model=LeadResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_lead_status(
    workspace_id: UUID,
    lead_id: int,
    payload: LeadStatusRequest,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LeadResponse:
    response.headers["Cache-Control"] = "no-store"
    return await LeadService(session, settings).update_status(
        user, workspace_id, lead_id, payload.followup_status
    )
