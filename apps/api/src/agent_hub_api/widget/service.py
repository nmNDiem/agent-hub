import hashlib
import json
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.agents.repository import AgentRepository
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.widget.repository import WebsiteChannel, WidgetRepository
from agent_hub_api.widget.schemas import (
    PublishedRevisionResponse,
    WidgetConfigRequest,
    WidgetConfigResponse,
    WidgetReadiness,
)
from agent_hub_api.workspaces.service import WorkspaceService


class WidgetAdminService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = WidgetRepository(session)

    async def _authorize(self, user: User, workspace_id: UUID, *, write: bool = False) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền cấu hình widget.",
            )

    async def _agent(
        self, workspace_id: UUID, public_agent_id: UUID, *, lock: bool = False
    ) -> Agent:
        agent = await self.repository.get_agent(workspace_id, public_agent_id, for_update=lock)
        if agent is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy chatbot.")
        return agent

    async def get(
        self, user: User, workspace_id: UUID, public_agent_id: UUID
    ) -> WidgetConfigResponse:
        await self._authorize(user, workspace_id)
        agent = await self._agent(workspace_id, public_agent_id)
        channel = await self.repository.get_channel(workspace_id, agent.id)
        return await self._response(agent, channel)

    async def update(
        self,
        user: User,
        workspace_id: UUID,
        public_agent_id: UUID,
        payload: WidgetConfigRequest,
    ) -> WidgetConfigResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_agent_id, lock=True)
            channel = await self.repository.ensure_channel(agent)
            agent.name = payload.display_name
            agent.greeting = payload.greeting
            agent.updated_at = datetime.now(UTC)
            channel.brand_color = payload.brand_color
            channel.launcher_position = payload.launcher_position
            channel.handoff_url = payload.handoff_url
            channel.handoff_label = payload.handoff_label if payload.handoff_url else None
            channel.connection.display_name = payload.display_name
            channel.updated_at = datetime.now(UTC)
            await self.repository.replace_domains(channel, payload.allowed_origins)
        return await self._response(agent, channel)

    async def publish(
        self, user: User, workspace_id: UUID, public_agent_id: UUID
    ) -> WidgetConfigResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_agent_id, lock=True)
            channel = await self.repository.get_channel(workspace_id, agent.id)
            if channel is None:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "WIDGET_NOT_CONFIGURED",
                    "Hãy cấu hình kênh Web trước khi xuất bản.",
                )
            domains = await self.repository.domains(channel)
            snapshot = await self._snapshot(agent, channel)
            readiness = self._readiness(
                domains,
                cast(list[int], snapshot["knowledge_base_ids"]),
                cast(dict[str, object], snapshot["catalog_scope"]),
            )
            if not readiness.can_publish:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "WIDGET_NOT_READY",
                    "Chatbot chưa đủ cấu hình để xuất bản.",
                )
            config_hash = self._config_hash(snapshot)
            active = await self.repository.active_revision(channel)
            if active is None or active.config_hash != config_hash:
                active = AgentRevision(
                    workspace_id=agent.workspace_id,
                    agent_id=agent.id,
                    revision_no=await self.repository.next_revision_no(agent),
                    name=agent.name,
                    greeting=agent.greeting,
                    safe_instructions=agent.safe_instructions,
                    default_locale=agent.default_locale,
                    catalog_scope_json=cast(dict[str, object], snapshot["catalog_scope"]),
                    knowledge_base_ids_json=cast(list[int], snapshot["knowledge_base_ids"]),
                    widget_config_json=cast(dict[str, object], snapshot["widget"]),
                    config_hash=config_hash,
                    created_by_user_id=user.id,
                )
                self.session.add(active)
                await self.session.flush()
                channel.active_revision_id = active.id
            channel.enabled = True
            channel.updated_at = datetime.now(UTC)
            agent.status = "published"
            agent.updated_at = datetime.now(UTC)
        return await self._response(agent, channel)

    async def pause(
        self, user: User, workspace_id: UUID, public_agent_id: UUID
    ) -> WidgetConfigResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_agent_id, lock=True)
            channel = await self.repository.get_channel(workspace_id, agent.id)
            if channel is None or channel.active_revision_id is None:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "WIDGET_NOT_PUBLISHED",
                    "Chatbot chưa được xuất bản.",
                )
            channel.enabled = False
            channel.updated_at = datetime.now(UTC)
            agent.status = "paused"
            agent.updated_at = datetime.now(UTC)
        return await self._response(agent, channel)

    async def _snapshot(self, agent: Agent, channel: WebsiteChannel) -> dict[str, object]:
        catalog_scope = await self._catalog_scope(agent)
        return {
            "name": agent.name,
            "greeting": agent.greeting,
            "safe_instructions": agent.safe_instructions,
            "default_locale": agent.default_locale,
            "catalog_scope": catalog_scope,
            "knowledge_base_ids": await self.repository.knowledge_base_ids(agent),
            "widget": {
                "brand_color": channel.brand_color,
                "launcher_position": channel.launcher_position,
                "handoff_url": channel.handoff_url,
                "handoff_label": channel.handoff_label,
            },
        }

    async def _catalog_scope(self, agent: Agent) -> dict[str, object]:
        locations, collections = await AgentRepository(self.session).assignment_maps(
            agent.workspace_id, [agent.id]
        )
        return {
            "location_ids": None if agent.all_locations else locations[agent.id],
            "collection_ids": None if agent.all_collections else collections[agent.id],
        }

    @staticmethod
    def _config_hash(snapshot: dict[str, object]) -> str:
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _readiness(
        domains: list[str], knowledge_ids: list[int], catalog_scope: dict[str, object]
    ) -> WidgetReadiness:
        location_ids = cast(list[int] | None, catalog_scope["location_ids"])
        collection_ids = cast(list[int] | None, catalog_scope["collection_ids"])
        has_catalog_scope = (location_ids is None or bool(location_ids)) and (
            collection_ids is None or bool(collection_ids)
        )
        has_origin = bool(domains)
        has_knowledge = bool(knowledge_ids)
        return WidgetReadiness(
            has_allowed_origin=has_origin,
            has_catalog_scope=has_catalog_scope,
            has_knowledge=has_knowledge,
            can_publish=has_origin and (has_catalog_scope or has_knowledge),
        )

    async def _response(
        self, agent: Agent, channel: WebsiteChannel | None
    ) -> WidgetConfigResponse:
        domains = await self.repository.domains(channel) if channel is not None else []
        knowledge_ids = await self.repository.knowledge_base_ids(agent)
        catalog_scope = await self._catalog_scope(agent)
        active = await self.repository.active_revision(channel) if channel is not None else None
        snapshot = await self._snapshot(agent, channel) if channel is not None else None
        draft_differs = (
            active is not None
            and snapshot is not None
            and active.config_hash != self._config_hash(snapshot)
        )
        readiness = self._readiness(domains, knowledge_ids, catalog_scope)
        embed_snippet = None
        if active is not None and self.settings.widget_public_base_url is not None:
            embed_snippet = (
                f'<script async src="{self.settings.widget_public_base_url}/widget/v1/loader.js" '
                f'data-agent-id="{agent.public_id}"></script>'
            )
        return WidgetConfigResponse(
            public_agent_id=agent.public_id,
            display_name=agent.name,
            greeting=agent.greeting,
            status=cast(Literal["draft", "published", "paused"], agent.status),
            brand_color=channel.brand_color if channel is not None else "#0F8F87",
            launcher_position=cast(
                Literal["left", "right"],
                channel.launcher_position if channel is not None else "right",
            ),
            allowed_origins=domains,
            handoff_url=channel.handoff_url if channel is not None else None,
            handoff_label=channel.handoff_label if channel is not None else None,
            enabled=channel.enabled if channel is not None else False,
            draft_differs=draft_differs,
            readiness=readiness,
            active_revision=(
                PublishedRevisionResponse(
                    revision_no=active.revision_no,
                    published_at=active.published_at,
                )
                if active is not None
                else None
            ),
            embed_snippet=embed_snippet,
        )
