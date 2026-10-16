from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import (
    Agent,
    AgentCatalogCollection,
    AgentLocation,
    AgentRevision,
)
from agent_hub_api.catalog.models import CatalogCollection, Location, Product
from agent_hub_api.channels.models import ChannelAgentBinding, ChannelConnection
from agent_hub_api.conversations.models import Conversation
from agent_hub_api.knowledge.models import (
    AgentKnowledgeBase,
    IngestionJob,
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)
from agent_hub_api.widget.models import WidgetDomain
from agent_hub_api.workspaces.models import WorkspaceMember

RELATIONSHIP_LIMIT = 20
AGENT_LIMIT = 50


@dataclass(frozen=True, slots=True)
class KnowledgeRow:
    agent_id: int
    base_id: int
    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class ChannelRow:
    agent_id: int
    connection_id: int
    provider: str
    display_name: str
    lifecycle_state: str
    health_state: str
    enabled: bool
    active_revision_id: int | None


@dataclass(frozen=True, slots=True)
class CatalogReferenceRow:
    agent_id: int
    item_id: int
    name: str


@dataclass(frozen=True, slots=True)
class ConversationCounts:
    total: int = 0
    open: int = 0
    pending: int = 0
    human_handling: int = 0


class WorkspaceOverviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def member_id(self, workspace_id: UUID, user_id: UUID) -> int | None:
        value = await self.session.scalar(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return int(value) if value is not None else None

    async def agents(self, workspace_id: UUID) -> tuple[list[Agent], int]:
        base = (Agent.workspace_id == workspace_id, Agent.archived_at.is_(None))
        total = int(
            await self.session.scalar(select(func.count()).select_from(Agent).where(*base)) or 0
        )
        items = list(
            (
                await self.session.scalars(
                    select(Agent).where(*base).order_by(Agent.public_id).limit(AGENT_LIMIT)
                )
            ).all()
        )
        return items, total

    async def latest_revisions(
        self, workspace_id: UUID, agent_ids: list[int]
    ) -> dict[int, AgentRevision]:
        if not agent_ids:
            return {}
        latest = (
            select(AgentRevision.agent_id, func.max(AgentRevision.id).label("revision_id"))
            .where(
                AgentRevision.workspace_id == workspace_id,
                AgentRevision.agent_id.in_(agent_ids),
            )
            .group_by(AgentRevision.agent_id)
            .subquery()
        )
        revisions = (
            await self.session.scalars(
                select(AgentRevision).join(
                    latest,
                    and_(
                        latest.c.agent_id == AgentRevision.agent_id,
                        latest.c.revision_id == AgentRevision.id,
                    ),
                )
            )
        ).all()
        return {revision.agent_id: revision for revision in revisions}

    async def knowledge(
        self, workspace_id: UUID, agent_ids: list[int]
    ) -> tuple[list[KnowledgeRow], dict[int, int], set[tuple[int, int]], set[tuple[int, int]]]:
        if not agent_ids:
            return [], {}, set(), set()
        totals = {
            agent_id: int(total)
            for agent_id, total in (
                await self.session.execute(
                    select(AgentKnowledgeBase.agent_id, func.count())
                    .join(
                        KnowledgeBase,
                        and_(
                            KnowledgeBase.workspace_id == AgentKnowledgeBase.workspace_id,
                            KnowledgeBase.id == AgentKnowledgeBase.knowledge_base_id,
                            KnowledgeBase.status == "active",
                        ),
                    )
                    .where(
                        AgentKnowledgeBase.workspace_id == workspace_id,
                        AgentKnowledgeBase.agent_id.in_(agent_ids),
                    )
                    .group_by(AgentKnowledgeBase.agent_id)
                )
            ).all()
        }
        ranked = (
            select(
                AgentKnowledgeBase.agent_id.label("agent_id"),
                KnowledgeBase.id.label("base_id"),
                KnowledgeBase.name.label("name"),
                KnowledgeBase.kind.label("kind"),
                func.row_number()
                .over(
                    partition_by=AgentKnowledgeBase.agent_id,
                    order_by=KnowledgeBase.id,
                )
                .label("position"),
            )
            .join(
                KnowledgeBase,
                and_(
                    KnowledgeBase.workspace_id == AgentKnowledgeBase.workspace_id,
                    KnowledgeBase.id == AgentKnowledgeBase.knowledge_base_id,
                    KnowledgeBase.status == "active",
                ),
            )
            .where(
                AgentKnowledgeBase.workspace_id == workspace_id,
                AgentKnowledgeBase.agent_id.in_(agent_ids),
            )
            .subquery()
        )
        rows = [
            KnowledgeRow(int(row.agent_id), int(row.base_id), str(row.name), str(row.kind))
            for row in (
                await self.session.execute(
                    select(ranked)
                    .where(ranked.c.position <= RELATIONSHIP_LIMIT)
                    .order_by(ranked.c.agent_id, ranked.c.base_id)
                )
            ).all()
        ]

        latest_versions = (
            select(
                KnowledgeDocument.workspace_id.label("workspace_id"),
                KnowledgeDocument.id.label("document_id"),
                func.max(KnowledgeDocumentVersion.version_no).label("version_no"),
            )
            .join(
                KnowledgeDocumentVersion,
                and_(
                    KnowledgeDocumentVersion.workspace_id == KnowledgeDocument.workspace_id,
                    KnowledgeDocumentVersion.document_id == KnowledgeDocument.id,
                ),
            )
            .where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.status == "active",
            )
            .group_by(KnowledgeDocument.workspace_id, KnowledgeDocument.id)
            .subquery()
        )
        assignment_join = and_(
            AgentKnowledgeBase.workspace_id == KnowledgeDocument.workspace_id,
            AgentKnowledgeBase.knowledge_base_id == KnowledgeDocument.knowledge_base_id,
        )
        latest_join = and_(
            latest_versions.c.workspace_id == KnowledgeDocumentVersion.workspace_id,
            latest_versions.c.document_id == KnowledgeDocumentVersion.document_id,
            latest_versions.c.version_no == KnowledgeDocumentVersion.version_no,
        )
        stale_bases = {
            (int(agent_id), int(base_id))
            for agent_id, base_id in (
                await self.session.execute(
                    select(AgentKnowledgeBase.agent_id, AgentKnowledgeBase.knowledge_base_id)
                    .join(KnowledgeDocument, assignment_join)
                    .join(
                        KnowledgeDocumentVersion,
                        and_(
                            KnowledgeDocumentVersion.workspace_id == KnowledgeDocument.workspace_id,
                            KnowledgeDocumentVersion.document_id == KnowledgeDocument.id,
                        ),
                    )
                    .join(latest_versions, latest_join)
                    .where(
                        AgentKnowledgeBase.workspace_id == workspace_id,
                        AgentKnowledgeBase.agent_id.in_(agent_ids),
                        KnowledgeDocumentVersion.review_due_at.is_not(None),
                        KnowledgeDocumentVersion.review_due_at <= datetime.now(UTC),
                    )
                    .distinct()
                )
            ).all()
        }
        failed_bases = {
            (int(agent_id), int(base_id))
            for agent_id, base_id in (
                await self.session.execute(
                    select(AgentKnowledgeBase.agent_id, AgentKnowledgeBase.knowledge_base_id)
                    .join(KnowledgeDocument, assignment_join)
                    .join(
                        KnowledgeDocumentVersion,
                        and_(
                            KnowledgeDocumentVersion.workspace_id == KnowledgeDocument.workspace_id,
                            KnowledgeDocumentVersion.document_id == KnowledgeDocument.id,
                        ),
                    )
                    .join(latest_versions, latest_join)
                    .join(
                        IngestionJob,
                        and_(
                            IngestionJob.workspace_id == KnowledgeDocumentVersion.workspace_id,
                            IngestionJob.document_id == KnowledgeDocumentVersion.document_id,
                            IngestionJob.document_version_id == KnowledgeDocumentVersion.id,
                        ),
                    )
                    .where(
                        AgentKnowledgeBase.workspace_id == workspace_id,
                        AgentKnowledgeBase.agent_id.in_(agent_ids),
                        IngestionJob.status == "failed",
                    )
                    .distinct()
                )
            ).all()
        }
        return rows, totals, stale_bases, failed_bases

    async def channels(
        self, workspace_id: UUID, agent_ids: list[int]
    ) -> tuple[list[ChannelRow], dict[tuple[int, str], int], dict[int, int]]:
        if not agent_ids:
            return [], {}, {}
        base_conditions = (
            ChannelAgentBinding.workspace_id == workspace_id,
            ChannelAgentBinding.agent_id.in_(agent_ids),
        )
        totals = {
            (int(agent_id), str(provider)): int(total)
            for agent_id, provider, total in (
                await self.session.execute(
                    select(
                        ChannelAgentBinding.agent_id,
                        ChannelConnection.provider,
                        func.count(),
                    )
                    .join(
                        ChannelConnection,
                        and_(
                            ChannelConnection.workspace_id == ChannelAgentBinding.workspace_id,
                            ChannelConnection.id == ChannelAgentBinding.connection_id,
                        ),
                    )
                    .where(*base_conditions)
                    .group_by(ChannelAgentBinding.agent_id, ChannelConnection.provider)
                )
            ).all()
        }
        ranked = (
            select(
                ChannelAgentBinding.agent_id.label("agent_id"),
                ChannelConnection.id.label("connection_id"),
                ChannelConnection.provider.label("provider"),
                ChannelConnection.display_name.label("display_name"),
                ChannelConnection.lifecycle_state.label("lifecycle_state"),
                ChannelConnection.health_state.label("health_state"),
                ChannelAgentBinding.enabled.label("enabled"),
                ChannelAgentBinding.active_revision_id.label("active_revision_id"),
                func.row_number()
                .over(
                    partition_by=(
                        ChannelAgentBinding.agent_id,
                        ChannelConnection.provider,
                    ),
                    order_by=ChannelConnection.id,
                )
                .label("position"),
            )
            .join(
                ChannelConnection,
                and_(
                    ChannelConnection.workspace_id == ChannelAgentBinding.workspace_id,
                    ChannelConnection.id == ChannelAgentBinding.connection_id,
                ),
            )
            .where(*base_conditions)
            .subquery()
        )
        rows = [
            ChannelRow(
                agent_id=int(row.agent_id),
                connection_id=int(row.connection_id),
                provider=str(row.provider),
                display_name=str(row.display_name),
                lifecycle_state=str(row.lifecycle_state),
                health_state=str(row.health_state),
                enabled=bool(row.enabled),
                active_revision_id=(
                    int(row.active_revision_id) if row.active_revision_id is not None else None
                ),
            )
            for row in (
                await self.session.execute(
                    select(ranked)
                    .where(ranked.c.position <= RELATIONSHIP_LIMIT)
                    .order_by(ranked.c.agent_id, ranked.c.provider, ranked.c.connection_id)
                )
            ).all()
        ]
        origin_counts = {
            int(connection_id): int(total)
            for connection_id, total in (
                await self.session.execute(
                    select(WidgetDomain.channel_id, func.count())
                    .where(
                        WidgetDomain.workspace_id == workspace_id,
                        WidgetDomain.channel_id.in_([row.connection_id for row in rows]),
                    )
                    .group_by(WidgetDomain.channel_id)
                )
            ).all()
        }
        return rows, totals, origin_counts

    async def catalog_references(
        self, workspace_id: UUID, agents: list[Agent]
    ) -> tuple[
        list[CatalogReferenceRow],
        dict[int, int],
        list[CatalogReferenceRow],
        dict[int, int],
        list[tuple[int, str]],
        int,
        list[tuple[int, str]],
        int,
    ]:
        agent_ids = [agent.id for agent in agents]
        if not agent_ids:
            return [], {}, [], {}, [], 0, [], 0
        location_rows, location_totals = await self._explicit_location_rows(workspace_id, agent_ids)
        collection_rows, collection_totals = await self._explicit_collection_rows(
            workspace_id, agent_ids
        )
        all_locations_total = int(
            await self.session.scalar(
                select(func.count())
                .select_from(Location)
                .where(Location.workspace_id == workspace_id, Location.is_active.is_(True))
            )
            or 0
        )
        all_locations = [
            (int(item_id), str(name))
            for item_id, name in (
                await self.session.execute(
                    select(Location.id, Location.name)
                    .where(Location.workspace_id == workspace_id, Location.is_active.is_(True))
                    .order_by(Location.id)
                    .limit(RELATIONSHIP_LIMIT)
                )
            ).all()
        ]
        all_collections_total = int(
            await self.session.scalar(
                select(func.count())
                .select_from(CatalogCollection)
                .where(
                    CatalogCollection.workspace_id == workspace_id,
                    CatalogCollection.is_active.is_(True),
                )
            )
            or 0
        )
        all_collections = [
            (int(item_id), str(name))
            for item_id, name in (
                await self.session.execute(
                    select(CatalogCollection.id, CatalogCollection.name)
                    .where(
                        CatalogCollection.workspace_id == workspace_id,
                        CatalogCollection.is_active.is_(True),
                    )
                    .order_by(CatalogCollection.id)
                    .limit(RELATIONSHIP_LIMIT)
                )
            ).all()
        ]
        return (
            location_rows,
            location_totals,
            collection_rows,
            collection_totals,
            all_locations,
            all_locations_total,
            all_collections,
            all_collections_total,
        )

    async def _explicit_location_rows(
        self, workspace_id: UUID, agent_ids: list[int]
    ) -> tuple[list[CatalogReferenceRow], dict[int, int]]:
        join_condition = and_(
            Location.workspace_id == AgentLocation.workspace_id,
            Location.id == AgentLocation.location_id,
            Location.is_active.is_(True),
        )
        totals = {
            int(agent_id): int(total)
            for agent_id, total in (
                await self.session.execute(
                    select(AgentLocation.agent_id, func.count())
                    .join(Location, join_condition)
                    .where(
                        AgentLocation.workspace_id == workspace_id,
                        AgentLocation.agent_id.in_(agent_ids),
                    )
                    .group_by(AgentLocation.agent_id)
                )
            ).all()
        }
        ranked = (
            select(
                AgentLocation.agent_id.label("agent_id"),
                Location.id.label("item_id"),
                Location.name.label("name"),
                func.row_number()
                .over(partition_by=AgentLocation.agent_id, order_by=Location.id)
                .label("position"),
            )
            .join(Location, join_condition)
            .where(
                AgentLocation.workspace_id == workspace_id,
                AgentLocation.agent_id.in_(agent_ids),
            )
            .subquery()
        )
        rows = [
            CatalogReferenceRow(int(row.agent_id), int(row.item_id), str(row.name))
            for row in (
                await self.session.execute(
                    select(ranked)
                    .where(ranked.c.position <= RELATIONSHIP_LIMIT)
                    .order_by(ranked.c.agent_id, ranked.c.item_id)
                )
            ).all()
        ]
        return rows, totals

    async def _explicit_collection_rows(
        self, workspace_id: UUID, agent_ids: list[int]
    ) -> tuple[list[CatalogReferenceRow], dict[int, int]]:
        join_condition = and_(
            CatalogCollection.workspace_id == AgentCatalogCollection.workspace_id,
            CatalogCollection.id == AgentCatalogCollection.collection_id,
            CatalogCollection.is_active.is_(True),
        )
        totals = {
            int(agent_id): int(total)
            for agent_id, total in (
                await self.session.execute(
                    select(AgentCatalogCollection.agent_id, func.count())
                    .join(CatalogCollection, join_condition)
                    .where(
                        AgentCatalogCollection.workspace_id == workspace_id,
                        AgentCatalogCollection.agent_id.in_(agent_ids),
                    )
                    .group_by(AgentCatalogCollection.agent_id)
                )
            ).all()
        }
        ranked = (
            select(
                AgentCatalogCollection.agent_id.label("agent_id"),
                CatalogCollection.id.label("item_id"),
                CatalogCollection.name.label("name"),
                func.row_number()
                .over(
                    partition_by=AgentCatalogCollection.agent_id,
                    order_by=CatalogCollection.id,
                )
                .label("position"),
            )
            .join(CatalogCollection, join_condition)
            .where(
                AgentCatalogCollection.workspace_id == workspace_id,
                AgentCatalogCollection.agent_id.in_(agent_ids),
            )
            .subquery()
        )
        rows = [
            CatalogReferenceRow(int(row.agent_id), int(row.item_id), str(row.name))
            for row in (
                await self.session.execute(
                    select(ranked)
                    .where(ranked.c.position <= RELATIONSHIP_LIMIT)
                    .order_by(ranked.c.agent_id, ranked.c.item_id)
                )
            ).all()
        ]
        return rows, totals

    async def conversation_counts(
        self,
        workspace_id: UUID,
        agent_ids: list[int],
        *,
        member_id: int,
        role: str,
        started_at: datetime,
    ) -> dict[int, ConversationCounts]:
        if not agent_ids:
            return {}
        statement = (
            select(
                Conversation.agent_id,
                func.count().label("total"),
                func.sum(case((Conversation.workflow_status == "open", 1), else_=0)).label(
                    "open_count"
                ),
                func.sum(case((Conversation.workflow_status == "pending", 1), else_=0)).label(
                    "pending_count"
                ),
                func.sum(case((Conversation.handling_mode == "human", 1), else_=0)).label(
                    "human_count"
                ),
            )
            .where(
                Conversation.workspace_id == workspace_id,
                Conversation.agent_id.in_(agent_ids),
                Conversation.lifecycle_state == "active",
                Conversation.last_message_at.is_not(None),
                Conversation.last_message_at >= started_at,
            )
            .group_by(Conversation.agent_id)
        )
        if role == "member":
            statement = statement.where(
                or_(
                    Conversation.assigned_member_id.is_(None),
                    Conversation.assigned_member_id == member_id,
                )
            )
        return {
            int(row.agent_id): ConversationCounts(
                total=int(row.total or 0),
                open=int(row.open_count or 0),
                pending=int(row.pending_count or 0),
                human_handling=int(row.human_count or 0),
            )
            for row in (await self.session.execute(statement)).all()
        }

    async def catalog_available(self, workspace_id: UUID) -> bool:
        checks = (
            select(Product.id).where(
                Product.workspace_id == workspace_id, Product.status == "active"
            ),
            select(Location.id).where(
                Location.workspace_id == workspace_id, Location.is_active.is_(True)
            ),
            select(CatalogCollection.id).where(
                CatalogCollection.workspace_id == workspace_id,
                CatalogCollection.is_active.is_(True),
            ),
        )
        for statement in checks:
            if await self.session.scalar(statement.limit(1)) is not None:
                return True
        return False
