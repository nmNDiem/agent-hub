from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import (
    Agent,
    AgentRevision,
)
from agent_hub_api.channels.models import ChannelAgentBinding, ChannelConnection
from agent_hub_api.knowledge.models import AgentKnowledgeBase, KnowledgeBase
from agent_hub_api.widget.models import WebsiteChannelConfig, WidgetDomain


@dataclass(slots=True)
class WebsiteChannel:
    connection: ChannelConnection
    binding: ChannelAgentBinding
    config: WebsiteChannelConfig

    @property
    def id(self) -> int:
        return self.connection.id

    @property
    def workspace_id(self) -> UUID:
        return self.connection.workspace_id

    @property
    def agent_id(self) -> int:
        return self.binding.agent_id

    @property
    def active_revision_id(self) -> int | None:
        return self.binding.active_revision_id

    @active_revision_id.setter
    def active_revision_id(self, value: int | None) -> None:
        self.binding.active_revision_id = value

    @property
    def enabled(self) -> bool:
        return self.binding.enabled and self.connection.lifecycle_state == "active"

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.binding.enabled = value

    @property
    def brand_color(self) -> str:
        return self.config.brand_color

    @brand_color.setter
    def brand_color(self, value: str) -> None:
        self.config.brand_color = value

    @property
    def launcher_position(self) -> str:
        return self.config.launcher_position

    @launcher_position.setter
    def launcher_position(self, value: str) -> None:
        self.config.launcher_position = value

    @property
    def handoff_url(self) -> str | None:
        return self.config.handoff_url

    @handoff_url.setter
    def handoff_url(self, value: str | None) -> None:
        self.config.handoff_url = value

    @property
    def handoff_label(self) -> str | None:
        return self.config.handoff_label

    @handoff_label.setter
    def handoff_label(self, value: str | None) -> None:
        self.config.handoff_label = value

    @property
    def updated_at(self) -> datetime:
        return self.config.updated_at

    @updated_at.setter
    def updated_at(self, value: datetime) -> None:
        self.connection.updated_at = value
        self.binding.updated_at = value
        self.config.updated_at = value


class WidgetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_agent(
        self, workspace_id: UUID, public_agent_id: UUID, *, for_update: bool = False
    ) -> Agent | None:
        statement = select(Agent).where(
            Agent.workspace_id == workspace_id,
            Agent.public_id == public_agent_id,
            Agent.archived_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.scalars(statement)).one_or_none()

    async def get_channel(self, workspace_id: UUID, agent_id: int) -> WebsiteChannel | None:
        row = (
            await self.session.execute(
                select(ChannelConnection, ChannelAgentBinding, WebsiteChannelConfig)
                .join(
                    ChannelAgentBinding,
                    (ChannelAgentBinding.workspace_id == ChannelConnection.workspace_id)
                    & (ChannelAgentBinding.connection_id == ChannelConnection.id),
                )
                .join(
                    WebsiteChannelConfig,
                    (WebsiteChannelConfig.workspace_id == ChannelConnection.workspace_id)
                    & (WebsiteChannelConfig.connection_id == ChannelConnection.id),
                )
                .where(
                    ChannelConnection.workspace_id == workspace_id,
                    ChannelConnection.provider == "web",
                    ChannelAgentBinding.agent_id == agent_id,
                )
            )
        ).one_or_none()
        return WebsiteChannel(*row) if row is not None else None

    async def ensure_channel(self, agent: Agent) -> WebsiteChannel:
        channel = await self.get_channel(agent.workspace_id, agent.id)
        if channel is None:
            connection = ChannelConnection(
                workspace_id=agent.workspace_id,
                provider="web",
                display_name=agent.name,
            )
            self.session.add(connection)
            await self.session.flush()
            binding = ChannelAgentBinding(
                workspace_id=agent.workspace_id,
                connection_id=connection.id,
                agent_id=agent.id,
            )
            config = WebsiteChannelConfig(
                workspace_id=agent.workspace_id,
                connection_id=connection.id,
            )
            self.session.add_all((binding, config))
            await self.session.flush()
            channel = WebsiteChannel(connection, binding, config)
        return channel

    async def domains(self, channel: WebsiteChannel) -> list[str]:
        return list(
            await self.session.scalars(
                select(WidgetDomain.normalized_origin)
                .where(
                    WidgetDomain.workspace_id == channel.workspace_id,
                    WidgetDomain.channel_id == channel.id,
                )
                .order_by(WidgetDomain.normalized_origin)
            )
        )

    async def replace_domains(self, channel: WebsiteChannel, origins: list[str]) -> None:
        await self.session.execute(
            delete(WidgetDomain).where(
                WidgetDomain.workspace_id == channel.workspace_id,
                WidgetDomain.channel_id == channel.id,
            )
        )
        self.session.add_all(
            [
                WidgetDomain(
                    workspace_id=channel.workspace_id,
                    channel_id=channel.id,
                    normalized_origin=origin,
                )
                for origin in origins
            ]
        )
        await self.session.flush()

    async def active_revision(self, channel: WebsiteChannel) -> AgentRevision | None:
        if channel.active_revision_id is None:
            return None
        result = await self.session.scalars(
            select(AgentRevision).where(
                AgentRevision.workspace_id == channel.workspace_id,
                AgentRevision.agent_id == channel.agent_id,
                AgentRevision.id == channel.active_revision_id,
            )
        )
        return result.one_or_none()

    async def next_revision_no(self, agent: Agent) -> int:
        current = await self.session.scalar(
            select(func.max(AgentRevision.revision_no)).where(
                AgentRevision.workspace_id == agent.workspace_id,
                AgentRevision.agent_id == agent.id,
            )
        )
        return int(current or 0) + 1

    async def knowledge_base_ids(self, agent: Agent) -> list[int]:
        return list(
            await self.session.scalars(
                select(AgentKnowledgeBase.knowledge_base_id)
                .join(
                    KnowledgeBase,
                    (KnowledgeBase.workspace_id == AgentKnowledgeBase.workspace_id)
                    & (KnowledgeBase.id == AgentKnowledgeBase.knowledge_base_id),
                )
                .where(
                    AgentKnowledgeBase.workspace_id == agent.workspace_id,
                    AgentKnowledgeBase.agent_id == agent.id,
                    KnowledgeBase.status == "active",
                )
                .order_by(AgentKnowledgeBase.knowledge_base_id)
            )
        )
