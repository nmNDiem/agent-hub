from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent
from agent_hub_api.channels.models import ChannelAgentBinding, ChannelConnection
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.conversations.repository import ConversationRepository, ConversationRow
from agent_hub_api.conversations.schemas import (
    ConversationAttachment,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationProductEvidence,
    ConversationSourceEvidence,
    ConversationSummary,
    DashboardActivityPoint,
    DashboardLeadSummary,
    DashboardResponse,
)
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.leads.models import Lead
from agent_hub_api.telemetry.service import TelemetryService
from agent_hub_api.widget.public_schemas import PublicGroundedResponse
from agent_hub_api.workspaces.models import Workspace
from agent_hub_api.workspaces.service import WorkspaceService


def _encode_cursor(activity_at: datetime, public_id: UUID) -> str:
    if activity_at.tzinfo is None:
        activity_at = activity_at.replace(tzinfo=UTC)
    raw = json.dumps(
        {"activity_at": activity_at.isoformat(), "public_id": str(public_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    if cursor is None:
        return None, None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        activity_at = datetime.fromisoformat(str(payload["activity_at"]))
        public_id = UUID(str(payload["public_id"]))
        if activity_at.tzinfo is None:
            raise ValueError
        return activity_at, public_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_CURSOR",
            "Con trỏ phân trang không hợp lệ.",
        ) from exc


def _period_bounds(timezone_name: str, days: int) -> tuple[datetime, datetime, list[date]]:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("Workspace timezone is invalid") from exc
    now_local = datetime.now(UTC).astimezone(timezone)
    dates = [now_local.date() - timedelta(days=offset) for offset in reversed(range(days))]
    started_local = datetime.combine(dates[0], time.min, tzinfo=timezone)
    return started_local.astimezone(UTC), now_local.astimezone(UTC), dates


def _summary(row: ConversationRow) -> ConversationSummary:
    conversation, agent_public_id, agent_name, message_count, preview, provider = row
    if conversation.last_message_at is None:
        raise RuntimeError("Listed conversation must have activity")
    return ConversationSummary(
        public_id=conversation.public_id,
        channel=cast(Literal["web", "facebook", "zalo"], provider),
        agent_public_id=agent_public_id,
        agent_name=agent_name,
        started_at=conversation.created_at,
        last_message_at=conversation.last_message_at,
        message_count=message_count,
        last_visitor_preview=preview[:240] if preview else None,
    )


class ConversationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = ConversationRepository(session)

    async def _authorize_admin(self, user: User, workspace_id: UUID) -> Workspace:
        workspace, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền xem lịch sử hội thoại.",
            )
        return workspace

    async def list(
        self,
        user: User,
        workspace_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        days: Literal[7, 30] | None,
        agent_public_id: UUID | None,
    ) -> ConversationListResponse:
        workspace = await self._authorize_admin(user, workspace_id)
        cursor_at, cursor_public_id = _decode_cursor(cursor)
        active_since = _period_bounds(workspace.timezone, days)[0] if days else None
        rows = await self.repository.list_rows(
            workspace_id,
            limit=limit + 1,
            active_since=active_since,
            agent_public_id=agent_public_id,
            cursor_at=cursor_at,
            cursor_public_id=cursor_public_id,
        )
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page:
            conversation = page[-1][0]
            assert conversation.last_message_at is not None
            next_cursor = _encode_cursor(conversation.last_message_at, conversation.public_id)
        return ConversationListResponse(
            items=[_summary(row) for row in page], next_cursor=next_cursor
        )

    async def detail(
        self, user: User, workspace_id: UUID, public_id: UUID
    ) -> ConversationDetailResponse:
        await self._authorize_admin(user, workspace_id)
        row = await self.repository.detail(workspace_id, public_id)
        if row is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy hội thoại.")
        conversation = row[0]
        messages = await self.repository.messages(workspace_id, conversation.id)
        uploads = await self.repository.attachments(workspace_id, conversation.id)
        uploads_by_key = {
            upload.attached_request_key: upload
            for upload in uploads
            if upload.attached_request_key is not None
        }
        response_messages: list[ConversationMessageResponse] = []
        for message in messages:
            stored = (
                PublicGroundedResponse.model_validate(message.response_json)
                if message.response_json is not None
                else None
            )
            upload = (
                uploads_by_key.get(message.request_key) if message.request_key is not None else None
            )
            attachment = None
            if upload is not None:
                attachment = ConversationAttachment(
                    content_type=cast(
                        Literal["image/jpeg", "image/png", "image/webp"],
                        upload.content_type,
                    ),
                    width=upload.width,
                    height=upload.height,
                    byte_size=upload.byte_size,
                    created_at=upload.created_at,
                )
            response_messages.append(
                ConversationMessageResponse(
                    role="user" if message.actor == "visitor" else "assistant",
                    text=message.text,
                    status=cast(
                        Literal["pending", "completed", "failed", "cancelled"],
                        message.status,
                    ),
                    created_at=message.created_at,
                    completed_at=message.completed_at,
                    attachment=attachment,
                    products=[
                        ConversationProductEvidence(
                            name=product.name,
                            sku=product.sku,
                            product_url=product.product_url,
                            price=product.price,
                            availability=product.availability,
                            options=product.options,
                        )
                        for product in stored.product_cards
                    ]
                    if stored
                    else [],
                    sources=[
                        ConversationSourceEvidence(
                            source_id=source.source_id,
                            title=source.title,
                            locator=source.locator,
                        )
                        for source in stored.sources
                    ]
                    if stored
                    else [],
                )
            )
        return ConversationDetailResponse(
            conversation=_summary(row),
            messages=response_messages,
            retention_until=conversation.retention_until,
        )

    async def dashboard(
        self, user: User, workspace_id: UUID, days: Literal[7, 30]
    ) -> DashboardResponse:
        workspace = await self._authorize_admin(user, workspace_id)
        period_started_at, period_ends_at, dates = _period_bounds(workspace.timezone, days)
        timezone = ZoneInfo(workspace.timezone)
        day_ranges = []
        for item in dates:
            started = datetime.combine(item, time.min, tzinfo=timezone).astimezone(UTC)
            ended = (
                datetime.combine(item, time.min, tzinfo=timezone) + timedelta(days=1)
            ).astimezone(UTC)
            day_ranges.append((item, started, ended))
        total_conversations = await self.session.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.workspace_id == workspace_id,
                Conversation.lifecycle_state == "active",
                Conversation.last_message_at.is_not(None),
                Conversation.created_at >= period_started_at,
                Conversation.created_at < period_ends_at,
            )
        )
        assistant_messages = await self.session.scalar(
            select(func.count(ConversationMessage.id)).where(
                ConversationMessage.workspace_id == workspace_id,
                ConversationMessage.actor == "assistant",
                ConversationMessage.status == "completed",
                ConversationMessage.completed_at >= period_started_at,
                ConversationMessage.completed_at < period_ends_at,
            )
        )
        active_agents = await self.session.scalar(
            select(func.count(Agent.id))
            .join(
                ChannelAgentBinding,
                and_(
                    ChannelAgentBinding.workspace_id == Agent.workspace_id,
                    ChannelAgentBinding.agent_id == Agent.id,
                ),
            )
            .join(
                ChannelConnection,
                and_(
                    ChannelConnection.workspace_id == ChannelAgentBinding.workspace_id,
                    ChannelConnection.id == ChannelAgentBinding.connection_id,
                ),
            )
            .where(
                Agent.workspace_id == workspace_id,
                Agent.status == "published",
                Agent.archived_at.is_(None),
                ChannelConnection.provider == "web",
                ChannelConnection.lifecycle_state == "active",
                ChannelAgentBinding.enabled.is_(True),
            )
        )
        activity_row = (
            await self.session.execute(
                select(
                    *[
                        func.coalesce(
                            func.sum(
                                case(
                                    (
                                        and_(
                                            Conversation.created_at >= started,
                                            Conversation.created_at < ended,
                                        ),
                                        1,
                                    ),
                                    else_=0,
                                )
                            ),
                            0,
                        )
                        for _, started, ended in day_ranges
                    ]
                ).where(
                    Conversation.workspace_id == workspace_id,
                    Conversation.lifecycle_state == "active",
                    Conversation.last_message_at.is_not(None),
                    Conversation.created_at >= period_started_at,
                    Conversation.created_at < period_ends_at,
                )
            )
        ).one()
        recent_rows = await self.repository.list_rows(workspace_id, limit=5)
        lead_rows = (
            await self.session.execute(
                select(Lead, Agent.name)
                .join(
                    Agent,
                    (Agent.workspace_id == Lead.workspace_id) & (Agent.id == Lead.agent_id),
                )
                .where(Lead.workspace_id == workspace_id)
                .order_by(Lead.created_at.desc(), Lead.id.desc())
                .limit(5)
            )
        ).all()
        return DashboardResponse(
            days=days,
            timezone=workspace.timezone,
            total_conversations=int(total_conversations or 0),
            assistant_messages=int(assistant_messages or 0),
            active_agents=int(active_agents or 0),
            enabled_web_channels=int(active_agents or 0),
            activity=[
                DashboardActivityPoint(date=item, conversations=int(activity_row[index]))
                for index, (item, _, _) in enumerate(day_ranges)
            ],
            recent_conversations=[_summary(row) for row in recent_rows],
            recent_leads=[
                DashboardLeadSummary(
                    name=lead.name,
                    agent_name=agent_name,
                    followup_status=cast(
                        Literal["new", "contacted", "closed"], lead.followup_status
                    ),
                    created_at=lead.created_at,
                )
                for lead, agent_name in lead_rows
            ],
            usage=await TelemetryService(self.session, self.settings).summary_for_workspace(
                workspace
            ),
        )
