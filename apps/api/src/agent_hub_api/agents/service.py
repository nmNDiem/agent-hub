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
    AgentIcon,
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

_DEFAULT_AGENT_COPY: dict[str, tuple[str, str]] = {
    "vi": (
        "Xin chào! Mình có thể giúp bạn tìm hiểu thông tin. Bạn đang quan tâm điều gì?",
        "Trò chuyện thân thiện, tự nhiên và chủ động. "
        "Trả lời rõ ràng, vừa đủ; ưu tiên nhu cầu của người dùng và đặt một câu hỏi tiếp theo "
        "khi điều đó giúp hỗ trợ tốt hơn. Chỉ sử dụng thông tin được cung cấp và nói rõ "
        "khi chưa thể xác minh.",
    ),
    "en": (
        "Hello! I can help you find and understand information. What would you like to know?",
        "Be a friendly, natural, and proactive assistant. Give clear, concise answers, "
        "focus on the user's needs, and ask a helpful follow-up question when appropriate. "
        "Use only the information provided and be transparent when something cannot be verified.",
    ),
}


def _default_agent_copy(locale: str) -> tuple[str, str]:
    language = locale.casefold().split("-", maxsplit=1)[0]
    return _DEFAULT_AGENT_COPY.get(language, _DEFAULT_AGENT_COPY["en"])


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
            icon=cast(AgentIcon, agent.icon),
            color=agent.color,
            greeting=agent.greeting,
            safe_instructions=agent.safe_instructions,
            default_locale=agent.default_locale,
            status=cast(AgentStatus, agent.status),
            follow_up_action_enabled=agent.follow_up_action_enabled,
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
        default_greeting, default_personality = _default_agent_copy(payload.default_locale)
        greeting = (
            payload.greeting
            if "greeting" in payload.model_fields_set
            else default_greeting
        )
        safe_instructions = (
            payload.safe_instructions
            if "safe_instructions" in payload.model_fields_set
            else default_personality
        )
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                agent = Agent(
                    public_id=new_uuid_v7(),
                    workspace_id=workspace_id,
                    name=payload.name,
                    icon=payload.icon,
                    color=payload.color,
                    greeting=greeting,
                    safe_instructions=safe_instructions,
                    default_locale=payload.default_locale,
                    follow_up_action_enabled=payload.follow_up_action_enabled,
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
                if field in {
                    "name",
                    "default_locale",
                    "icon",
                    "color",
                    "follow_up_action_enabled",
                } and value is None:
                    raise ApiError(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "VALIDATION_ERROR",
                        f"{field} cannot be null",
                    )
                setattr(agent, field, value)
            agent.updated_at = datetime.now(UTC)
        return await self._response_for(agent)

    async def archive(self, user: User, workspace_id: UUID, public_id: UUID) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_id)
            archived_at = datetime.now(UTC)
            agent.archived_at = archived_at
            agent.updated_at = archived_at

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
