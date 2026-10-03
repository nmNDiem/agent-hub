from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import (
    Agent,
    AgentRevision,
    AgentWebChannel,
    WidgetDomain,
)
from agent_hub_api.knowledge.models import AgentKnowledgeBase, KnowledgeBase


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

    async def get_channel(self, workspace_id: UUID, agent_id: int) -> AgentWebChannel | None:
        result = await self.session.scalars(
            select(AgentWebChannel).where(
                AgentWebChannel.workspace_id == workspace_id,
                AgentWebChannel.agent_id == agent_id,
            )
        )
        return result.one_or_none()

    async def ensure_channel(self, agent: Agent) -> AgentWebChannel:
        channel = await self.get_channel(agent.workspace_id, agent.id)
        if channel is None:
            channel = AgentWebChannel(workspace_id=agent.workspace_id, agent_id=agent.id)
            self.session.add(channel)
            await self.session.flush()
        return channel

    async def domains(self, channel: AgentWebChannel) -> list[str]:
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

    async def replace_domains(self, channel: AgentWebChannel, origins: list[str]) -> None:
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

    async def active_revision(self, channel: AgentWebChannel) -> AgentRevision | None:
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
