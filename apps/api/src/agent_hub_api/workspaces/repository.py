from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.workspaces.models import Workspace, WorkspaceMember


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[tuple[Workspace, str]]:
        result = await self.session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id, Workspace.status == "active")
            .order_by(Workspace.created_at, Workspace.id)
        )
        return [(workspace, role) for workspace, role in result.all()]

    async def get_for_user(
        self, user_id: UUID, workspace_id: UUID
    ) -> tuple[Workspace, str] | None:
        result = await self.session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                Workspace.id == workspace_id,
                WorkspaceMember.user_id == user_id,
                Workspace.status == "active",
            )
        )
        row = result.one_or_none()
        return row._tuple() if row is not None else None

    async def add_workspace_with_owner(
        self, workspace: Workspace, owner_membership: WorkspaceMember
    ) -> None:
        self.session.add(workspace)
        await self.session.flush()
        self.session.add(owner_membership)
