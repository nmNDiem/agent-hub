from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.models import User
from agent_hub_api.identity.schemas import UserResponse
from agent_hub_api.workspaces.models import Workspace, WorkspaceMember
from agent_hub_api.workspaces.repository import WorkspaceRepository
from agent_hub_api.workspaces.schemas import (
    CreateWorkspaceRequest,
    MeResponse,
    UpdateWorkspaceRequest,
    WorkspaceResponse,
)

WorkspaceRole = Literal["owner", "admin", "member"]


def workspace_response(workspace: Workspace, role: str) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        slug=workspace.slug,
        display_name=workspace.display_name,
        timezone=workspace.timezone,
        role=cast(WorkspaceRole, role),
        created_at=workspace.created_at,
    )


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WorkspaceRepository(session)

    async def list_for_user(self, user_id: UUID) -> list[WorkspaceResponse]:
        workspaces = await self.repository.list_for_user(user_id)
        return [workspace_response(workspace, role) for workspace, role in workspaces]

    async def me(self, user: User) -> MeResponse:
        profile = UserResponse(
            id=user.id,
            email=user.normalized_email,
            email_verified=user.email_verified_at is not None,
        )
        return MeResponse(user=profile, workspaces=await self.list_for_user(user.id))

    async def create(self, user: User, request: CreateWorkspaceRequest) -> WorkspaceResponse:
        workspace = Workspace(
            id=new_uuid_v7(),
            slug=request.slug,
            display_name=request.display_name,
            timezone=request.timezone,
        )
        membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        try:
            async with self.session.begin():
                await self.repository.add_workspace_with_owner(workspace, membership)
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "WORKSPACE_SLUG_UNAVAILABLE",
                "Đường dẫn cửa hàng đã được sử dụng.",
            ) from exc
        return workspace_response(workspace, "owner")

    async def get_for_user(self, user_id: UUID, workspace_id: UUID) -> tuple[Workspace, str]:
        workspace_access = await self.repository.get_for_user(user_id, workspace_id)
        if workspace_access is None:
            raise ApiError(
                status.HTTP_404_NOT_FOUND,
                "NOT_FOUND",
                "Không tìm thấy cửa hàng.",
            )
        return workspace_access

    async def update(
        self, user: User, workspace_id: UUID, request: UpdateWorkspaceRequest
    ) -> WorkspaceResponse:
        async with self.session.begin():
            workspace, role = await self.get_for_user(user.id, workspace_id)
            if role not in {"owner", "admin"}:
                raise ApiError(
                    status.HTTP_403_FORBIDDEN,
                    "FORBIDDEN",
                    "Bạn không có quyền thay đổi cửa hàng này.",
                )
            workspace.display_name = request.display_name
            workspace.timezone = request.timezone
            workspace.updated_at = datetime.now(UTC)
        return workspace_response(workspace, role)
