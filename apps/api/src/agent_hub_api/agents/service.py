from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent
from agent_hub_api.agents.repository import AgentRepository
from agent_hub_api.agents.schemas import (
    AgentCatalogScopeRequest,
    AgentCatalogScopeResponse,
    AgentCreateRequest,
    AgentListResponse,
    AgentResponse,
    AgentStatus,
    AgentUpdateRequest,
)
from agent_hub_api.catalog.models import CatalogCollection, Location
from agent_hub_api.catalog.read_models import AuthorizedCatalogScope
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.service import WorkspaceService


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AgentRepository(session)

    async def _authorize(self, user: User, workspace_id: UUID, *, write: bool = False) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền thay đổi agent.",
            )

    async def _agent(self, workspace_id: UUID, public_id: UUID) -> Agent:
        agent = await self.repository.get_active(workspace_id, public_id)
        if agent is None:
            raise ApiError(
                status.HTTP_404_NOT_FOUND,
                "NOT_FOUND",
                "Không tìm thấy agent.",
            )
        return agent

    @staticmethod
    def _response(
        agent: Agent,
        location_ids: list[int],
        collection_ids: list[int],
    ) -> AgentResponse:
        return AgentResponse(
            public_id=agent.public_id,
            name=agent.name,
            greeting=agent.greeting,
            safe_instructions=agent.safe_instructions,
            default_locale=agent.default_locale,
            status=cast(AgentStatus, agent.status),
            catalog_scope=AgentCatalogScopeResponse(
                location_ids=None if agent.all_locations else location_ids,
                collection_ids=None if agent.all_collections else collection_ids,
            ),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    async def _response_for(self, agent: Agent) -> AgentResponse:
        locations, collections = await self.repository.assignment_maps(
            agent.workspace_id, [agent.id]
        )
        return self._response(agent, locations[agent.id], collections[agent.id])

    async def list(self, user: User, workspace_id: UUID) -> AgentListResponse:
        await self._authorize(user, workspace_id)
        agents = await self.repository.list_active(workspace_id)
        locations, collections = await self.repository.assignment_maps(
            workspace_id, [agent.id for agent in agents]
        )
        return AgentListResponse(
            items=[
                self._response(agent, locations[agent.id], collections[agent.id])
                for agent in agents
            ]
        )

    async def get(self, user: User, workspace_id: UUID, public_id: UUID) -> AgentResponse:
        await self._authorize(user, workspace_id)
        return await self._response_for(await self._agent(workspace_id, public_id))

    async def create(
        self, user: User, workspace_id: UUID, payload: AgentCreateRequest
    ) -> AgentResponse:
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                agent = Agent(
                    public_id=new_uuid_v7(),
                    workspace_id=workspace_id,
                    name=payload.name,
                    greeting=payload.greeting,
                    safe_instructions=payload.safe_instructions,
                    default_locale=payload.default_locale,
                    created_by_user_id=user.id,
                )
                self.session.add(agent)
                await self.session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "AGENT_CREATE_CONFLICT",
                "Không thể tạo agent.",
            ) from exc
        return await self._response_for(agent)

    async def update(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        payload: AgentUpdateRequest,
    ) -> AgentResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_id)
            for field in payload.model_fields_set:
                value = getattr(payload, field)
                if field in {"name", "default_locale"} and value is None:
                    raise ApiError(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "VALIDATION_ERROR",
                        f"{field} cannot be null",
                    )
                setattr(agent, field, value)
            agent.updated_at = datetime.now(UTC)
        return await self._response_for(agent)

    async def replace_catalog_scope(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        payload: AgentCatalogScopeRequest,
    ) -> AgentResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_id)
            await self._validate_scope_ids(
                workspace_id,
                location_ids=payload.location_ids,
                collection_ids=payload.collection_ids,
            )
            await self.repository.replace_assignments(
                agent,
                location_ids=payload.location_ids,
                collection_ids=payload.collection_ids,
            )
            agent.updated_at = datetime.now(UTC)
        return await self._response_for(agent)

    async def _validate_scope_ids(
        self,
        workspace_id: UUID,
        *,
        location_ids: Sequence[int] | None,
        collection_ids: Sequence[int] | None,
    ) -> None:
        if location_ids:
            found = set(
                await self.session.scalars(
                    select(Location.id).where(
                        Location.workspace_id == workspace_id,
                        Location.id.in_(location_ids),
                        Location.is_active.is_(True),
                    )
                )
            )
            if found != set(location_ids):
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy location.",
                )
        if collection_ids:
            found = set(
                await self.session.scalars(
                    select(CatalogCollection.id).where(
                        CatalogCollection.workspace_id == workspace_id,
                        CatalogCollection.id.in_(collection_ids),
                        CatalogCollection.is_active.is_(True),
                    )
                )
            )
            if found != set(collection_ids):
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy collection.",
                )


async def resolve_agent_catalog_scope(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    public_agent_id: UUID,
) -> AuthorizedCatalogScope:
    """Resolve immutable catalog authorization after the caller validates agent context."""

    repository = AgentRepository(session)
    agent = await repository.get_active(workspace_id, public_agent_id)
    if agent is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy agent.")
    location_ids, collection_ids = await repository.active_scope_ids(agent)
    return AuthorizedCatalogScope(
        workspace_id=workspace_id,
        allowed_location_ids=location_ids,
        allowed_collection_ids=collection_ids,
    )
