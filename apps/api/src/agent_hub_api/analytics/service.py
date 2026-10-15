from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from statistics import fmean
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from agent_hub_api.agents.models import Agent
from agent_hub_api.analytics.models import AnalyticsEvent
from agent_hub_api.analytics.schemas import (
    AnalyticsActivityPoint,
    AnalyticsAgentOption,
    AnalyticsBreakdown,
    AnalyticsDeliveryOutcomes,
    AnalyticsLeadConversion,
    AnalyticsProductInterest,
    AnalyticsResolution,
    AnalyticsResponseTiming,
    AnalyticsSummary,
    OperationalAnalyticsResponse,
)
from agent_hub_api.catalog.models import Product
from agent_hub_api.channels.models import ChannelConnection, OutboundDelivery
from agent_hub_api.conversations.models import (
    Conversation,
    ConversationAuditEvent,
    ConversationMessage,
)
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.leads.models import Lead
from agent_hub_api.workspaces.service import WorkspaceService

Channel = Literal["web", "facebook", "zalo"]


@dataclass
class _Activity:
    conversations: set[int] = field(default_factory=set)
    inbound_messages: int = 0
    completed_replies: int = 0


@dataclass
class _Breakdown:
    key: str
    label: str
    conversations: set[int] = field(default_factory=set)
    inbound_messages: int = 0
    completed_replies: int = 0
    delivery: dict[str, int] = field(
        default_factory=lambda: {
            "accepted": 0,
            "delivered": 0,
            "failed_retryable": 0,
            "failed_terminal": 0,
        }
    )
    has_provider_delivery: bool = False


def _period_bounds(timezone_name: str, days: int) -> tuple[datetime, datetime, list[date]]:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("Workspace timezone is invalid") from exc
    now_local = datetime.now(UTC).astimezone(timezone)
    dates = [now_local.date() - timedelta(days=offset) for offset in reversed(range(days))]
    started_local = datetime.combine(dates[0], time.min, tzinfo=timezone)
    return started_local.astimezone(UTC), now_local.astimezone(UTC), dates


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _is_handoff(details: object) -> bool:
    if not isinstance(details, dict):
        return False
    change = details.get("handling_mode")
    return isinstance(change, dict) and change.get("to") == "human"


def _timing(values: list[float]) -> AnalyticsResponseTiming:
    return AnalyticsResponseTiming(
        average_seconds=round(fmean(values), 1) if values else None,
        sample_count=len(values),
    )


def _delivery(values: dict[str, int]) -> AnalyticsDeliveryOutcomes:
    return AnalyticsDeliveryOutcomes(
        accepted=values["accepted"],
        delivered=values["delivered"],
        failed_retryable=values["failed_retryable"],
        failed_terminal=values["failed_terminal"],
    )


def _breakdown_response(item: _Breakdown) -> AnalyticsBreakdown:
    return AnalyticsBreakdown(
        key=item.key,
        label=item.label,
        conversations=len(item.conversations),
        inbound_messages=item.inbound_messages,
        completed_replies=item.completed_replies,
        delivery=_delivery(item.delivery) if item.has_provider_delivery else None,
    )


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def report(
        self,
        user: User,
        workspace_id: UUID,
        *,
        days: Literal[7, 30],
        channel: Channel | None,
        agent_public_id: UUID | None,
    ) -> OperationalAnalyticsResponse:
        workspace, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền xem phân tích.",
            )
        agent_id: int | None = None
        if agent_public_id is not None:
            agent_id = await self.session.scalar(
                select(Agent.id).where(
                    Agent.workspace_id == workspace_id,
                    Agent.public_id == agent_public_id,
                    Agent.archived_at.is_(None),
                )
            )
            if agent_id is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy chatbot.",
                )

        started_at, ends_at, dates = _period_bounds(workspace.timezone, days)
        timezone = ZoneInfo(workspace.timezone)
        cohort_statement = (
            select(
                ConversationMessage.conversation_id.label("conversation_id"),
                func.min(ConversationMessage.created_at).label("first_inbound_at"),
                Conversation.agent_id.label("agent_id"),
                ChannelConnection.provider.label("channel"),
            )
            .join(
                Conversation,
                and_(
                    Conversation.workspace_id == ConversationMessage.workspace_id,
                    Conversation.id == ConversationMessage.conversation_id,
                ),
            )
            .join(
                ChannelConnection,
                and_(
                    ChannelConnection.workspace_id == Conversation.workspace_id,
                    ChannelConnection.id == Conversation.channel_connection_id,
                ),
            )
            .where(
                ConversationMessage.workspace_id == workspace_id,
                ConversationMessage.direction == "inbound",
                ConversationMessage.created_at >= started_at,
                ConversationMessage.created_at < ends_at,
                Conversation.lifecycle_state == "active",
            )
            .group_by(
                ConversationMessage.conversation_id,
                Conversation.agent_id,
                ChannelConnection.provider,
            )
        )
        if channel is not None:
            cohort_statement = cohort_statement.where(ChannelConnection.provider == channel)
        if agent_id is not None:
            cohort_statement = cohort_statement.where(Conversation.agent_id == agent_id)
        cohort = cohort_statement.subquery()

        agent_rows = (
            await self.session.execute(
                select(Agent.public_id, Agent.name)
                .where(Agent.workspace_id == workspace_id, Agent.archived_at.is_(None))
                .order_by(Agent.name, Agent.public_id)
            )
        ).all()
        cohort_rows = (
            await self.session.execute(
                select(
                    Conversation.id,
                    Conversation.workflow_status,
                    cohort.c.first_inbound_at,
                    cohort.c.channel,
                    Agent.public_id,
                    Agent.name,
                )
                .join(cohort, cohort.c.conversation_id == Conversation.id)
                .join(
                    Agent,
                    and_(
                        Agent.workspace_id == Conversation.workspace_id,
                        Agent.id == Conversation.agent_id,
                    ),
                )
            )
        ).all()
        cohort_ids = {int(row.id) for row in cohort_rows}

        activity = {item: _Activity() for item in dates}
        by_channel: dict[str, _Breakdown] = {}
        by_agent: dict[str, _Breakdown] = {}
        inbound_messages = 0
        completed_replies = 0
        failed_replies = 0
        message_rows = (
            await self.session.execute(
                select(
                    ConversationMessage.conversation_id,
                    ConversationMessage.actor,
                    ConversationMessage.direction,
                    ConversationMessage.status,
                    ConversationMessage.safe_error_code,
                    ConversationMessage.created_at,
                    ConversationMessage.completed_at,
                    ChannelConnection.provider,
                    Agent.public_id,
                    Agent.name,
                )
                .join(
                    Conversation,
                    and_(
                        Conversation.workspace_id == ConversationMessage.workspace_id,
                        Conversation.id == ConversationMessage.conversation_id,
                    ),
                )
                .join(
                    ChannelConnection,
                    and_(
                        ChannelConnection.workspace_id == Conversation.workspace_id,
                        ChannelConnection.id == Conversation.channel_connection_id,
                    ),
                )
                .join(
                    Agent,
                    and_(
                        Agent.workspace_id == Conversation.workspace_id,
                        Agent.id == Conversation.agent_id,
                    ),
                )
                .join(cohort, cohort.c.conversation_id == ConversationMessage.conversation_id)
                .where(
                    ConversationMessage.workspace_id == workspace_id,
                    Conversation.lifecycle_state == "active",
                    or_(
                        and_(
                            ConversationMessage.created_at >= started_at,
                            ConversationMessage.created_at < ends_at,
                        ),
                        and_(
                            ConversationMessage.completed_at >= started_at,
                            ConversationMessage.completed_at < ends_at,
                        ),
                    ),
                    *([ChannelConnection.provider == channel] if channel is not None else []),
                    *([Conversation.agent_id == agent_id] if agent_id is not None else []),
                )
            )
        ).all()
        for message_row in message_rows:
            channel_key = str(message_row.provider)
            agent_key = str(message_row.public_id)
            channel_item = by_channel.setdefault(
                channel_key, _Breakdown(key=channel_key, label=channel_key.capitalize())
            )
            agent_item = by_agent.setdefault(
                agent_key, _Breakdown(key=agent_key, label=str(message_row.name))
            )
            created_at = _aware(message_row.created_at)
            if (
                message_row.direction == "inbound"
                and started_at <= created_at < ends_at
                and int(message_row.conversation_id) in cohort_ids
            ):
                day = created_at.astimezone(timezone).date()
                activity[day].conversations.add(int(message_row.conversation_id))
                activity[day].inbound_messages += 1
                inbound_messages += 1
                for item in (channel_item, agent_item):
                    item.conversations.add(int(message_row.conversation_id))
                    item.inbound_messages += 1
            completed_at = (
                _aware(message_row.completed_at) if message_row.completed_at is not None else None
            )
            if (
                message_row.direction == "outbound"
                and message_row.actor in {"assistant", "human"}
                and message_row.status == "completed"
                and completed_at is not None
                and started_at <= completed_at < ends_at
            ):
                day = completed_at.astimezone(timezone).date()
                activity[day].completed_replies += 1
                completed_replies += 1
                channel_item.completed_replies += 1
                agent_item.completed_replies += 1
            if (
                message_row.actor == "assistant"
                and message_row.status in {"failed", "cancelled"}
                and message_row.safe_error_code != "HUMAN_TAKEOVER"
                and started_at <= created_at < ends_at
            ):
                failed_replies += 1

        human_message_rows = (
            await self.session.execute(
                select(ConversationMessage.conversation_id, ConversationMessage.completed_at)
                .join(cohort, cohort.c.conversation_id == ConversationMessage.conversation_id)
                .where(
                    ConversationMessage.workspace_id == workspace_id,
                    ConversationMessage.actor == "human",
                    ConversationMessage.status == "completed",
                    ConversationMessage.completed_at.is_not(None),
                    ConversationMessage.completed_at < ends_at,
                )
            )
        ).all()
        human_conversations = {int(row.conversation_id) for row in human_message_rows}
        human_times: dict[int, list[datetime]] = {}
        for human_row in human_message_rows:
            human_times.setdefault(int(human_row.conversation_id), []).append(
                _aware(human_row.completed_at)
            )

        audit_rows = (
            await self.session.execute(
                select(
                    ConversationAuditEvent.conversation_id,
                    ConversationAuditEvent.details_json,
                    ConversationAuditEvent.created_at,
                )
                .join(cohort, cohort.c.conversation_id == ConversationAuditEvent.conversation_id)
                .where(
                    ConversationAuditEvent.workspace_id == workspace_id,
                    ConversationAuditEvent.event_type == "state_changed",
                    ConversationAuditEvent.created_at < ends_at,
                )
                .order_by(ConversationAuditEvent.created_at, ConversationAuditEvent.id)
            )
        ).all()
        handoff_conversations: set[int] = set()
        handoffs_in_period: list[tuple[int, datetime]] = []
        for audit_row in audit_rows:
            if not _is_handoff(audit_row.details_json):
                continue
            conversation_id = int(audit_row.conversation_id)
            handoff_at = _aware(audit_row.created_at)
            handoff_conversations.add(conversation_id)
            if started_at <= handoff_at < ends_at:
                handoffs_in_period.append((conversation_id, handoff_at))

        ai_only_resolved = 0
        human_handled_resolved = 0
        unresolved = 0
        for cohort_row in cohort_rows:
            conversation_id = int(cohort_row.id)
            if cohort_row.workflow_status != "resolved":
                unresolved += 1
            elif conversation_id in human_conversations or conversation_id in handoff_conversations:
                human_handled_resolved += 1
            else:
                ai_only_resolved += 1

        response_message = aliased(ConversationMessage)
        first_response_rows = (
            await self.session.execute(
                select(
                    cohort.c.first_inbound_at,
                    func.min(response_message.completed_at).label("responded_at"),
                )
                .outerjoin(
                    response_message,
                    and_(
                        response_message.workspace_id == workspace_id,
                        response_message.conversation_id == cohort.c.conversation_id,
                        response_message.direction == "outbound",
                        response_message.actor.in_(["assistant", "human"]),
                        response_message.status == "completed",
                        response_message.completed_at >= cohort.c.first_inbound_at,
                        response_message.completed_at < ends_at,
                    ),
                )
                .group_by(cohort.c.conversation_id, cohort.c.first_inbound_at)
            )
        ).all()
        first_response_seconds = [
            (_aware(row.responded_at) - _aware(row.first_inbound_at)).total_seconds()
            for row in first_response_rows
            if row.responded_at is not None
            and _aware(row.responded_at) >= _aware(row.first_inbound_at)
        ]
        human_response_seconds: list[float] = []
        for conversation_id, handoff_at in handoffs_in_period:
            response_at = next(
                (
                    item
                    for item in sorted(human_times.get(conversation_id, []))
                    if item >= handoff_at
                ),
                None,
            )
            if response_at is not None:
                human_response_seconds.append((response_at - handoff_at).total_seconds())

        converted = int(
            await self.session.scalar(
                select(func.count(func.distinct(Lead.conversation_id)))
                .join(cohort, cohort.c.conversation_id == Lead.conversation_id)
                .where(
                    Lead.workspace_id == workspace_id,
                    Lead.created_at >= started_at,
                    Lead.created_at < ends_at,
                )
            )
            or 0
        )

        product_statement = (
            select(
                AnalyticsEvent.product_id,
                Product.name,
                func.count(AnalyticsEvent.id).label("impressions"),
                func.count(func.distinct(AnalyticsEvent.conversation_id)).label("conversations"),
            )
            .join(
                Product,
                and_(
                    Product.workspace_id == AnalyticsEvent.workspace_id,
                    Product.id == AnalyticsEvent.product_id,
                ),
            )
            .where(
                AnalyticsEvent.workspace_id == workspace_id,
                AnalyticsEvent.event_type == "product_impression",
                AnalyticsEvent.occurred_at >= started_at,
                AnalyticsEvent.occurred_at < ends_at,
            )
            .group_by(AnalyticsEvent.product_id, Product.name)
            .order_by(func.count(AnalyticsEvent.id).desc(), Product.name, AnalyticsEvent.product_id)
            .limit(10)
        )
        if channel is not None:
            product_statement = product_statement.where(AnalyticsEvent.channel == channel)
        if agent_id is not None:
            product_statement = product_statement.where(AnalyticsEvent.agent_id == agent_id)
        product_rows = (await self.session.execute(product_statement)).all()

        delivery_statement = (
            select(
                ChannelConnection.provider,
                Agent.public_id,
                OutboundDelivery.state,
                func.count(OutboundDelivery.id),
            )
            .join(
                ConversationMessage,
                and_(
                    ConversationMessage.workspace_id == OutboundDelivery.workspace_id,
                    ConversationMessage.id == OutboundDelivery.message_id,
                ),
            )
            .join(
                Conversation,
                and_(
                    Conversation.workspace_id == ConversationMessage.workspace_id,
                    Conversation.id == ConversationMessage.conversation_id,
                ),
            )
            .join(
                ChannelConnection,
                and_(
                    ChannelConnection.workspace_id == OutboundDelivery.workspace_id,
                    ChannelConnection.id == OutboundDelivery.connection_id,
                ),
            )
            .join(
                Agent,
                and_(
                    Agent.workspace_id == Conversation.workspace_id,
                    Agent.id == Conversation.agent_id,
                ),
            )
            .where(
                OutboundDelivery.workspace_id == workspace_id,
                OutboundDelivery.created_at >= started_at,
                OutboundDelivery.created_at < ends_at,
                OutboundDelivery.state.in_(
                    ["accepted", "delivered", "failed_retryable", "failed_terminal"]
                ),
                *([ChannelConnection.provider == channel] if channel is not None else []),
                *([Conversation.agent_id == agent_id] if agent_id is not None else []),
            )
            .group_by(ChannelConnection.provider, Agent.public_id, OutboundDelivery.state)
        )
        for provider, public_id, delivery_state, count in (
            await self.session.execute(delivery_statement)
        ).all():
            channel_key = str(provider)
            agent_key = str(public_id)
            channel_item = by_channel.setdefault(
                channel_key, _Breakdown(key=channel_key, label=channel_key.capitalize())
            )
            agent_name = next(
                (str(name) for candidate, name in agent_rows if candidate == public_id), agent_key
            )
            agent_item = by_agent.setdefault(agent_key, _Breakdown(key=agent_key, label=agent_name))
            for item in (channel_item, agent_item):
                item.has_provider_delivery = True
                item.delivery[str(delivery_state)] = int(count)

        cohort_count = len(cohort_ids)
        return OperationalAnalyticsResponse(
            days=days,
            timezone=workspace.timezone,
            period_started_at=started_at,
            period_ends_at=ends_at,
            channel=channel,
            agent_public_id=agent_public_id,
            summary=AnalyticsSummary(
                conversations=cohort_count,
                inbound_messages=inbound_messages,
                completed_replies=completed_replies,
                failed_replies=failed_replies,
            ),
            first_response=_timing(first_response_seconds),
            human_response=_timing(human_response_seconds),
            resolution=AnalyticsResolution(
                ai_only_resolved=ai_only_resolved,
                human_handled_resolved=human_handled_resolved,
                unresolved=unresolved,
                handoffs=len(handoffs_in_period),
            ),
            lead_conversion=AnalyticsLeadConversion(
                converted_conversations=converted,
                eligible_conversations=cohort_count,
                rate=round(converted / cohort_count, 4) if cohort_count else None,
            ),
            activity=[
                AnalyticsActivityPoint(
                    date=item,
                    conversations=len(activity[item].conversations),
                    inbound_messages=activity[item].inbound_messages,
                    completed_replies=activity[item].completed_replies,
                )
                for item in dates
            ],
            by_channel=[_breakdown_response(item) for item in by_channel.values()],
            by_agent=[_breakdown_response(item) for item in by_agent.values()],
            product_interest=[
                AnalyticsProductInterest(
                    product_id=int(row.product_id),
                    product_name=str(row.name),
                    impressions=int(row.impressions),
                    conversations=int(row.conversations),
                )
                for row in product_rows
            ],
            agent_options=[
                AnalyticsAgentOption(public_id=public_id, name=name)
                for public_id, name in agent_rows
            ],
        )
