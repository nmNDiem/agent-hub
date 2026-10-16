from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.overview_repository import (
    AGENT_LIMIT,
    RELATIONSHIP_LIMIT,
    CatalogReferenceRow,
    ChannelRow,
    ConversationCounts,
    WorkspaceOverviewRepository,
)
from agent_hub_api.workspaces.overview_schemas import (
    AttentionReason,
    OverviewAgent,
    OverviewCapabilities,
    OverviewCatalogCapability,
    OverviewCatalogReference,
    OverviewCatalogReferenceCollection,
    OverviewCatalogScope,
    OverviewChannelCollection,
    OverviewChannelGroups,
    OverviewChannelItem,
    OverviewConversationActivity,
    OverviewDependencies,
    OverviewDependency,
    OverviewKnowledgeCollection,
    OverviewKnowledgeItem,
    OverviewPublishedRevision,
    OverviewWebsiteReadiness,
    WorkspaceOverviewResponse,
)
from agent_hub_api.workspaces.service import WorkspaceService


def _window_start(timezone_name: str, days: Literal[7, 30]) -> datetime:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("Workspace timezone is invalid") from exc
    local_today = datetime.now(UTC).astimezone(timezone).date()
    started = datetime.combine(local_today - timedelta(days=days - 1), time.min, timezone)
    return started.astimezone(UTC)


def _reference_collection(
    rows: list[CatalogReferenceRow], total: int, *, all_accessible: bool
) -> OverviewCatalogReferenceCollection:
    return OverviewCatalogReferenceCollection(
        items=[OverviewCatalogReference(id=row.item_id, name=row.name) for row in rows],
        total=total,
        truncated=total > RELATIONSHIP_LIMIT,
        all_accessible=all_accessible,
    )


class WorkspaceOverviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = WorkspaceOverviewRepository(session)
        self.workspace_service = WorkspaceService(session)

    async def get(
        self, user: User, workspace_id: UUID, days: Literal[7, 30]
    ) -> WorkspaceOverviewResponse:
        workspace, raw_role = await self.workspace_service.get_for_user(user.id, workspace_id)
        role = cast(Literal["owner", "admin", "member"], raw_role)
        member_id = await self.repository.member_id(workspace_id, user.id)
        if member_id is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy workspace.")

        generated_at = datetime.now(UTC)
        window_started_at = _window_start(workspace.timezone, days)
        agents, agent_total = await self.repository.agents(workspace_id)
        agent_ids = [agent.id for agent in agents]
        revisions = await self.repository.latest_revisions(workspace_id, agent_ids)
        (
            knowledge_rows,
            knowledge_totals,
            stale_bases,
            failed_bases,
        ) = await self.repository.knowledge(workspace_id, agent_ids)
        channel_rows, channel_totals, origin_counts = await self.repository.channels(
            workspace_id, agent_ids
        )
        (
            location_rows,
            location_totals,
            collection_rows,
            collection_totals,
            all_locations,
            all_locations_total,
            all_collections,
            all_collections_total,
        ) = await self.repository.catalog_references(workspace_id, agents)
        conversations = await self.repository.conversation_counts(
            workspace_id,
            agent_ids,
            member_id=member_id,
            role=role,
            started_at=window_started_at,
        )
        catalog_available = await self.repository.catalog_available(workspace_id)

        knowledge_by_agent: dict[int, list[OverviewKnowledgeItem]] = defaultdict(list)
        for knowledge_row in knowledge_rows:
            item_state: Literal["ready", "stale", "failed"] = "ready"
            if (knowledge_row.agent_id, knowledge_row.base_id) in stale_bases:
                item_state = "stale"
            if (knowledge_row.agent_id, knowledge_row.base_id) in failed_bases:
                item_state = "failed"
            knowledge_by_agent[knowledge_row.agent_id].append(
                OverviewKnowledgeItem(
                    id=knowledge_row.base_id,
                    name=knowledge_row.name,
                    kind=cast(Literal["shop", "faq", "policy", "general"], knowledge_row.kind),
                    state=item_state,
                )
            )

        channels_by_agent: dict[int, dict[str, list[ChannelRow]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for channel_row in channel_rows:
            channels_by_agent[channel_row.agent_id][channel_row.provider].append(channel_row)
        locations_by_agent: dict[int, list[CatalogReferenceRow]] = defaultdict(list)
        for location_row in location_rows:
            locations_by_agent[location_row.agent_id].append(location_row)
        collections_by_agent: dict[int, list[CatalogReferenceRow]] = defaultdict(list)
        for collection_row in collection_rows:
            collections_by_agent[collection_row.agent_id].append(collection_row)

        overview_agents: list[OverviewAgent] = []
        for agent in agents:
            channel_groups = {
                provider: self._channels(
                    channels_by_agent[agent.id][provider],
                    channel_totals.get((agent.id, provider), 0),
                )
                for provider in ("web", "facebook", "zalo")
            }
            knowledge_total = knowledge_totals.get(agent.id, 0)
            if agent.all_locations:
                agent_locations = [
                    CatalogReferenceRow(agent.id, item_id, name) for item_id, name in all_locations
                ]
                agent_location_total = all_locations_total
            else:
                agent_locations = locations_by_agent[agent.id]
                agent_location_total = location_totals.get(agent.id, 0)
            if agent.all_collections:
                agent_collections = [
                    CatalogReferenceRow(agent.id, item_id, name)
                    for item_id, name in all_collections
                ]
                agent_collection_total = all_collections_total
            else:
                agent_collections = collections_by_agent[agent.id]
                agent_collection_total = collection_totals.get(agent.id, 0)

            has_catalog_scope = (agent.all_locations or agent_location_total > 0) and (
                agent.all_collections or agent_collection_total > 0
            )
            web_channels = channels_by_agent[agent.id]["web"]
            has_origin = any(
                origin_counts.get(channel.connection_id, 0) > 0 for channel in web_channels
            )
            readiness = OverviewWebsiteReadiness(
                configured=bool(web_channels),
                has_allowed_origin=has_origin,
                has_knowledge=knowledge_total > 0,
                has_catalog_scope=has_catalog_scope,
                can_publish=has_origin and (knowledge_total > 0 or has_catalog_scope),
            )
            attention: list[AttentionReason] = []
            if any(item[0] == agent.id for item in stale_bases):
                attention.append("knowledge_stale")
            if any(item[0] == agent.id for item in failed_bases):
                attention.append("knowledge_failed")
            if readiness.configured and not readiness.can_publish:
                attention.append("website_not_ready")
            flattened_channels = [
                channel
                for provider_rows in channels_by_agent[agent.id].values()
                for channel in provider_rows
            ]
            if any(
                channel.lifecycle_state == "revoked" or not channel.enabled
                for channel in flattened_channels
            ):
                attention.append("channel_disconnected")
            if any(row.health_state not in {"unknown", "healthy"} for row in flattened_channels):
                attention.append("channel_degraded")
            counts = conversations.get(agent.id, ConversationCounts())
            if counts.human_handling > 0 or counts.pending > 0:
                attention.append("handover_pending")

            revision = revisions.get(agent.id)
            overview_agents.append(
                OverviewAgent(
                    public_id=agent.public_id,
                    name=agent.name,
                    lifecycle_state=cast(Literal["draft", "published", "paused"], agent.status),
                    updated_at=agent.updated_at,
                    active_revision=(
                        OverviewPublishedRevision(
                            id=revision.id,
                            revision_no=revision.revision_no,
                            published_at=revision.published_at,
                        )
                        if revision is not None
                        else None
                    ),
                    knowledge=OverviewKnowledgeCollection(
                        items=knowledge_by_agent[agent.id],
                        total=knowledge_total,
                        truncated=knowledge_total > RELATIONSHIP_LIMIT,
                    ),
                    channels=OverviewChannelGroups(
                        web=channel_groups["web"],
                        facebook=channel_groups["facebook"],
                        zalo=channel_groups["zalo"],
                    ),
                    catalog_scope=OverviewCatalogScope(
                        available=catalog_available and has_catalog_scope,
                        locations=_reference_collection(
                            agent_locations,
                            agent_location_total,
                            all_accessible=agent.all_locations,
                        ),
                        collections=_reference_collection(
                            agent_collections,
                            agent_collection_total,
                            all_accessible=agent.all_collections,
                        ),
                    ),
                    website_readiness=readiness,
                    conversations=OverviewConversationActivity(
                        total=counts.total,
                        open=counts.open,
                        pending=counts.pending,
                        human_handling=counts.human_handling,
                    ),
                    attention_reasons=attention,
                )
            )

        return WorkspaceOverviewResponse(
            workspace_id=workspace.id,
            workspace_slug=workspace.slug,
            workspace_name=workspace.display_name,
            role=role,
            generated_at=generated_at,
            days=days,
            window_started_at=window_started_at,
            capabilities=OverviewCapabilities(
                catalog=OverviewCatalogCapability(
                    available=catalog_available,
                    can_setup=not catalog_available and role in {"owner", "admin"},
                )
            ),
            dependencies=OverviewDependencies(
                agents=OverviewDependency(state="ready"),
                knowledge=OverviewDependency(state="ready"),
                channels=OverviewDependency(state="ready"),
                conversations=OverviewDependency(state="ready"),
                catalog=OverviewDependency(state="ready"),
            ),
            agent_total=agent_total,
            agents_truncated=agent_total > AGENT_LIMIT,
            agents=overview_agents,
        )

    @staticmethod
    def _channels(rows: list[ChannelRow], total: int) -> OverviewChannelCollection:
        return OverviewChannelCollection(
            items=[
                OverviewChannelItem(
                    id=row.connection_id,
                    provider=cast(Literal["web", "facebook", "zalo"], row.provider),
                    display_name=row.display_name,
                    lifecycle_state=cast(Literal["active", "revoked"], row.lifecycle_state),
                    health_state=cast(
                        Literal[
                            "unknown",
                            "healthy",
                            "permission_expired",
                            "reauth_required",
                            "webhook_subscription_failure",
                            "delivery_unknown",
                        ],
                        row.health_state,
                    ),
                    enabled=row.enabled,
                    active_revision_id=row.active_revision_id,
                )
                for row in rows
            ],
            total=total,
            truncated=total > RELATIONSHIP_LIMIT,
        )
