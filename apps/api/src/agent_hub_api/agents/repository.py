from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent, AgentCatalogCollection, AgentLocation
from agent_hub_api.catalog.models import CatalogCollection, Location


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self, workspace_id: UUID) -> list[Agent]:
        return list(
            (
                await self.session.scalars(
                    select(Agent)
                    .where(Agent.workspace_id == workspace_id, Agent.archived_at.is_(None))
                    .order_by(Agent.created_at, Agent.id)
                )
            ).all()
        )

    async def get_active(self, workspace_id: UUID, public_id: UUID) -> Agent | None:
        result = await self.session.scalars(
            select(Agent).where(
                Agent.workspace_id == workspace_id,
                Agent.public_id == public_id,
                Agent.archived_at.is_(None),
            )
        )
        return result.one_or_none()

    async def assignment_maps(
        self, workspace_id: UUID, agent_ids: list[int]
    ) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
        locations: dict[int, list[int]] = {agent_id: [] for agent_id in agent_ids}
        collections: dict[int, list[int]] = {agent_id: [] for agent_id in agent_ids}
        if not agent_ids:
            return locations, collections
        location_rows = (
            await self.session.execute(
                select(AgentLocation.agent_id, AgentLocation.location_id)
                .where(
                    AgentLocation.workspace_id == workspace_id,
                    AgentLocation.agent_id.in_(agent_ids),
                )
                .order_by(AgentLocation.agent_id, AgentLocation.location_id)
            )
        ).all()
        collection_rows = (
            await self.session.execute(
                select(AgentCatalogCollection.agent_id, AgentCatalogCollection.collection_id)
                .where(
                    AgentCatalogCollection.workspace_id == workspace_id,
                    AgentCatalogCollection.agent_id.in_(agent_ids),
                )
                .order_by(
                    AgentCatalogCollection.agent_id,
                    AgentCatalogCollection.collection_id,
                )
            )
        ).all()
        for agent_id, location_id in location_rows:
            locations[agent_id].append(location_id)
        for agent_id, collection_id in collection_rows:
            collections[agent_id].append(collection_id)
        return locations, collections

    async def replace_assignments(
        self,
        agent: Agent,
        *,
        location_ids: list[int] | None,
        collection_ids: list[int] | None,
    ) -> None:
        await self.session.execute(
            delete(AgentLocation).where(
                AgentLocation.workspace_id == agent.workspace_id,
                AgentLocation.agent_id == agent.id,
            )
        )
        await self.session.execute(
            delete(AgentCatalogCollection).where(
                AgentCatalogCollection.workspace_id == agent.workspace_id,
                AgentCatalogCollection.agent_id == agent.id,
            )
        )
        agent.all_locations = location_ids is None
        agent.all_collections = collection_ids is None
        self.session.add_all(
            [
                AgentLocation(
                    workspace_id=agent.workspace_id,
                    agent_id=agent.id,
                    location_id=location_id,
                )
                for location_id in location_ids or []
            ]
        )
        self.session.add_all(
            [
                AgentCatalogCollection(
                    workspace_id=agent.workspace_id,
                    agent_id=agent.id,
                    collection_id=collection_id,
                )
                for collection_id in collection_ids or []
            ]
        )
        await self.session.flush()

    async def active_scope_ids(
        self, agent: Agent
    ) -> tuple[frozenset[int] | None, frozenset[int] | None]:
        location_ids: frozenset[int] | None = None
        collection_ids: frozenset[int] | None = None
        if not agent.all_locations:
            location_ids = frozenset(
                await self.session.scalars(
                    select(AgentLocation.location_id)
                    .join(
                        Location,
                        (Location.workspace_id == AgentLocation.workspace_id)
                        & (Location.id == AgentLocation.location_id),
                    )
                    .where(
                        AgentLocation.workspace_id == agent.workspace_id,
                        AgentLocation.agent_id == agent.id,
                        Location.is_active.is_(True),
                    )
                )
            )
        if not agent.all_collections:
            collection_ids = frozenset(
                await self.session.scalars(
                    select(AgentCatalogCollection.collection_id)
                    .join(
                        CatalogCollection,
                        (CatalogCollection.workspace_id == AgentCatalogCollection.workspace_id)
                        & (CatalogCollection.id == AgentCatalogCollection.collection_id),
                    )
                    .where(
                        AgentCatalogCollection.workspace_id == agent.workspace_id,
                        AgentCatalogCollection.agent_id == agent.id,
                        CatalogCollection.is_active.is_(True),
                    )
                )
            )
        return location_ids, collection_ids
