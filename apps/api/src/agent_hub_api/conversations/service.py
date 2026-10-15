from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent
from agent_hub_api.channels.models import (
    ChannelAgentBinding,
    ChannelConnection,
    ChannelMessageMapping,
    ChannelResponseJob,
    ChannelThreadMapping,
    OutboundDelivery,
)
from agent_hub_api.conversations.models import (
    Conversation,
    ConversationAuditEvent,
    ConversationMessage,
    ConversationNote,
    ConversationReadState,
    ConversationTag,
    ConversationTagLink,
)
from agent_hub_api.conversations.repository import ConversationRepository, ConversationRow
from agent_hub_api.conversations.schemas import (
    ConversationAttachment,
    ConversationDeliveryResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationNoteRequest,
    ConversationNoteResponse,
    ConversationProductEvidence,
    ConversationSourceEvidence,
    ConversationStateRequest,
    ConversationSummary,
    ConversationTagRequest,
    ConversationTagResponse,
    DashboardActivityPoint,
    DashboardLeadSummary,
    DashboardResponse,
    HumanReplyRequest,
    InboxMemberListResponse,
    InboxMemberResponse,
)
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.leads.models import Lead
from agent_hub_api.telemetry.service import TelemetryService
from agent_hub_api.widget.public_schemas import PublicGroundedResponse
from agent_hub_api.workspaces.models import Workspace, WorkspaceMember
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


def _summary(
    row: ConversationRow, tags: list[ConversationTag] | None = None
) -> ConversationSummary:
    (
        conversation,
        agent_public_id,
        agent_name,
        message_count,
        preview,
        provider,
        email,
        unread,
        contact_public_id,
    ) = row
    if conversation.last_message_at is None:
        raise RuntimeError("Listed conversation must have activity")
    return ConversationSummary(
        public_id=conversation.public_id,
        contact_public_id=contact_public_id,
        channel=cast(Literal["web", "facebook", "zalo"], provider),
        agent_public_id=agent_public_id,
        agent_name=agent_name,
        started_at=conversation.created_at,
        last_message_at=conversation.last_message_at,
        message_count=message_count,
        last_visitor_preview=preview[:240] if preview else None,
        workflow_status=cast(Literal["open", "pending", "resolved"], conversation.workflow_status),
        handling_mode=cast(Literal["ai", "human", "paused"], conversation.handling_mode),
        state_version=conversation.state_version,
        assigned_member_id=conversation.assigned_member_id,
        assigned_member_email=email,
        unread_count=unread,
        tags=[ConversationTagResponse(id=tag.id, name=tag.name) for tag in tags or []],
    )


class ConversationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = ConversationRepository(session)

    async def _access(self, user: User, workspace_id: UUID) -> tuple[Workspace, WorkspaceMember]:
        workspace, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        member = await self.repository.member(workspace_id, user.id)
        if member is None or member.role != role:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy cửa hàng.")
        return workspace, member

    async def list(
        self,
        user: User,
        workspace_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        days: Literal[7, 30] | None,
        agent_public_id: UUID | None,
        provider: Literal["web", "facebook", "zalo"] | None = None,
        workflow_status: Literal["open", "pending", "resolved"] | None = None,
        assigned_member_id: int | None = None,
        tag_id: int | None = None,
    ) -> ConversationListResponse:
        workspace, member = await self._access(user, workspace_id)
        cursor_at, cursor_public_id = _decode_cursor(cursor)
        active_since = _period_bounds(workspace.timezone, days)[0] if days else None
        rows = await self.repository.list_rows(
            workspace_id,
            limit=limit + 1,
            member_id=member.id,
            role=member.role,
            active_since=active_since,
            agent_public_id=agent_public_id,
            provider=provider,
            workflow_status=workflow_status,
            assigned_member_id=assigned_member_id,
            tag_id=tag_id,
            cursor_at=cursor_at,
            cursor_public_id=cursor_public_id,
        )
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page:
            conversation = page[-1][0]
            assert conversation.last_message_at is not None
            next_cursor = _encode_cursor(conversation.last_message_at, conversation.public_id)
        tags = await self.repository.tags_for_conversations(
            workspace_id, [row[0].id for row in page]
        )
        return ConversationListResponse(
            items=[_summary(row, tags.get(row[0].id)) for row in page], next_cursor=next_cursor
        )

    async def detail(
        self, user: User, workspace_id: UUID, public_id: UUID
    ) -> ConversationDetailResponse:
        _, member = await self._access(user, workspace_id)
        row = await self.repository.detail(
            workspace_id, public_id, member_id=member.id, role=member.role
        )
        if row is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy hội thoại.")
        conversation = row[0]
        messages = await self.repository.messages(workspace_id, conversation.id)
        uploads = await self.repository.attachments(workspace_id, conversation.id)
        deliveries = (
            {
                item.message_id: item
                for item in await self.session.scalars(
                    select(OutboundDelivery).where(
                        OutboundDelivery.workspace_id == workspace_id,
                        OutboundDelivery.message_id.in_([message.id for message in messages]),
                    )
                )
            }
            if messages
            else {}
        )
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
                    id=message.id,
                    role=cast(
                        Literal["user", "assistant", "human"],
                        "user" if message.actor == "visitor" else message.actor,
                    ),
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
                    delivery=(
                        ConversationDeliveryResponse(
                            state=cast(
                                Literal[
                                    "queued",
                                    "sending",
                                    "accepted",
                                    "delivered",
                                    "failed_retryable",
                                    "failed_terminal",
                                ],
                                deliveries[message.id].state,
                            ),
                            attempt_count=deliveries[message.id].attempt_count,
                            max_attempts=deliveries[message.id].max_attempts,
                            next_attempt_at=deliveries[message.id].next_attempt_at,
                            safe_error_code=deliveries[message.id].safe_error_code,
                        )
                        if message.id in deliveries
                        else None
                    ),
                )
            )
        tags = await self.repository.tags_for_conversations(workspace_id, [conversation.id])
        notes = await self.repository.notes(workspace_id, conversation.id)
        return ConversationDetailResponse(
            conversation=_summary(row, tags.get(conversation.id)),
            messages=response_messages,
            retention_until=conversation.retention_until,
            notes=[
                ConversationNoteResponse(
                    id=note.id,
                    author_member_id=note.author_member_id,
                    author_email=email,
                    body=note.body,
                    created_at=note.created_at,
                )
                for note, email in notes
            ],
        )

    async def members(self, user: User, workspace_id: UUID) -> InboxMemberListResponse:
        _, current_member = await self._access(user, workspace_id)
        rows = await self.repository.members(workspace_id)
        if current_member.role == "member":
            rows = [row for row in rows if row[0].id == current_member.id]
        return InboxMemberListResponse(
            items=[
                InboxMemberResponse(
                    id=member.id,
                    user_id=member.user_id,
                    email=email,
                    role=cast(Literal["owner", "admin", "member"], member.role),
                )
                for member, email in rows
            ]
        )

    async def _locked_conversation(
        self, workspace_id: UUID, public_id: UUID, member: WorkspaceMember
    ) -> Conversation:
        conversation = (
            await self.session.scalars(
                select(Conversation)
                .where(
                    Conversation.workspace_id == workspace_id,
                    Conversation.public_id == public_id,
                    Conversation.lifecycle_state == "active",
                )
                .with_for_update()
            )
        ).one_or_none()
        if conversation is None or (
            member.role == "member" and conversation.assigned_member_id not in {None, member.id}
        ):
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy hội thoại.")
        return conversation

    async def mark_read(self, user: User, workspace_id: UUID, public_id: UUID) -> None:
        async with self.session.begin():
            _, member = await self._access(user, workspace_id)
            conversation = await self._locked_conversation(workspace_id, public_id, member)
            sequence = int(
                await self.session.scalar(
                    select(func.coalesce(func.max(ConversationMessage.sequence_no), 0)).where(
                        ConversationMessage.workspace_id == workspace_id,
                        ConversationMessage.conversation_id == conversation.id,
                    )
                )
                or 0
            )
            read_state = (
                await self.session.scalars(
                    select(ConversationReadState).where(
                        ConversationReadState.conversation_id == conversation.id,
                        ConversationReadState.member_id == member.id,
                    )
                )
            ).one_or_none()
            if read_state is None:
                self.session.add(
                    ConversationReadState(
                        workspace_id=workspace_id,
                        conversation_id=conversation.id,
                        member_id=member.id,
                        last_read_sequence=sequence,
                    )
                )
            else:
                read_state.last_read_sequence = max(read_state.last_read_sequence, sequence)
                read_state.updated_at = datetime.now(UTC)

    async def update_state(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        request: ConversationStateRequest,
    ) -> None:
        now = datetime.now(UTC)
        async with self.session.begin():
            _, member = await self._access(user, workspace_id)
            conversation = await self._locked_conversation(workspace_id, public_id, member)
            if conversation.state_version != request.state_version:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "STALE_CONVERSATION",
                    "Hội thoại vừa được cập nhật. Vui lòng tải lại.",
                )
            target_assignee = conversation.assigned_member_id
            if request.clear_assignment:
                target_assignee = None
            elif request.assigned_member_id is not None:
                target_assignee = request.assigned_member_id
            if member.role == "member":
                if target_assignee != member.id:
                    raise ApiError(
                        status.HTTP_403_FORBIDDEN,
                        "FORBIDDEN",
                        "Bạn chỉ có thể nhận hội thoại chưa được phân công.",
                    )
                if conversation.assigned_member_id not in {None, member.id}:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "ALREADY_ASSIGNED",
                        "Hội thoại đã được người khác nhận.",
                    )
            if target_assignee is not None:
                assignee = await self.session.get(WorkspaceMember, target_assignee)
                if assignee is None or assignee.workspace_id != workspace_id:
                    raise ApiError(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "INVALID_ASSIGNEE",
                        "Người phụ trách không hợp lệ.",
                    )
            target_mode = request.handling_mode or conversation.handling_mode
            if target_mode == "human" and target_assignee is None:
                target_assignee = member.id
            changes: dict[str, object] = {}
            for key, value in (
                ("workflow_status", request.workflow_status),
                ("handling_mode", request.handling_mode),
            ):
                if value is not None and getattr(conversation, key) != value:
                    changes[key] = {"from": getattr(conversation, key), "to": value}
                    setattr(conversation, key, value)
            if conversation.assigned_member_id != target_assignee:
                changes["assigned_member_id"] = {
                    "from": conversation.assigned_member_id,
                    "to": target_assignee,
                }
                conversation.assigned_member_id = target_assignee
            if not changes:
                return
            conversation.state_version += 1
            self.session.add(
                ConversationAuditEvent(
                    workspace_id=workspace_id,
                    conversation_id=conversation.id,
                    actor_member_id=member.id,
                    event_type="state_changed",
                    details_json=changes,
                )
            )
            if conversation.handling_mode != "ai":
                jobs = await self.session.scalars(
                    select(ChannelResponseJob).where(
                        ChannelResponseJob.workspace_id == workspace_id,
                        ChannelResponseJob.conversation_id == conversation.id,
                        ChannelResponseJob.state.in_(["queued", "failed_retryable"]),
                    )
                )
                for job in jobs:
                    job.state = "suppressed"
                    job.safe_error_code = "HUMAN_TAKEOVER"
                    job.updated_at = now

    async def add_note(
        self, user: User, workspace_id: UUID, public_id: UUID, request: ConversationNoteRequest
    ) -> None:
        async with self.session.begin():
            _, member = await self._access(user, workspace_id)
            conversation = await self._locked_conversation(workspace_id, public_id, member)
            if member.role == "member" and conversation.assigned_member_id != member.id:
                raise ApiError(
                    status.HTTP_403_FORBIDDEN,
                    "FORBIDDEN",
                    "Hãy nhận hội thoại trước khi thêm ghi chú.",
                )
            self.session.add(
                ConversationNote(
                    workspace_id=workspace_id,
                    conversation_id=conversation.id,
                    author_member_id=member.id,
                    body=request.body,
                )
            )
            self.session.add(
                ConversationAuditEvent(
                    workspace_id=workspace_id,
                    conversation_id=conversation.id,
                    actor_member_id=member.id,
                    event_type="note_added",
                    details_json={},
                )
            )

    async def add_tag(
        self, user: User, workspace_id: UUID, public_id: UUID, request: ConversationTagRequest
    ) -> None:
        normalized = request.name.casefold()
        async with self.session.begin():
            _, member = await self._access(user, workspace_id)
            conversation = await self._locked_conversation(workspace_id, public_id, member)
            if member.role == "member" and conversation.assigned_member_id != member.id:
                raise ApiError(
                    status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Hãy nhận hội thoại trước khi gắn thẻ."
                )
            tag = (
                await self.session.scalars(
                    select(ConversationTag).where(
                        ConversationTag.workspace_id == workspace_id,
                        ConversationTag.normalized_name == normalized,
                    )
                )
            ).one_or_none()
            if tag is None:
                tag = ConversationTag(
                    workspace_id=workspace_id, name=request.name, normalized_name=normalized
                )
                self.session.add(tag)
                await self.session.flush()
            exists = await self.session.scalar(
                select(ConversationTagLink.id).where(
                    ConversationTagLink.conversation_id == conversation.id,
                    ConversationTagLink.tag_id == tag.id,
                )
            )
            if exists is None:
                self.session.add(
                    ConversationTagLink(
                        workspace_id=workspace_id, conversation_id=conversation.id, tag_id=tag.id
                    )
                )
                self.session.add(
                    ConversationAuditEvent(
                        workspace_id=workspace_id,
                        conversation_id=conversation.id,
                        actor_member_id=member.id,
                        event_type="tag_added",
                        details_json={"tag_id": tag.id},
                    )
                )

    async def reply(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        request_key: str,
        request: HumanReplyRequest,
    ) -> None:
        digest = hashlib.sha256(request.text.encode()).hexdigest()
        now = datetime.now(UTC)
        async with self.session.begin():
            _, member = await self._access(user, workspace_id)
            conversation = await self._locked_conversation(workspace_id, public_id, member)
            if conversation.handling_mode != "human":
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "HUMAN_TAKEOVER_REQUIRED",
                    "Hãy tiếp quản hội thoại trước khi trả lời.",
                )
            if member.role == "member" and conversation.assigned_member_id != member.id:
                raise ApiError(
                    status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Hội thoại chưa được giao cho bạn."
                )
            key = f"human:{request_key}"
            existing = await self.session.scalar(
                select(ConversationMessage).where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.request_key == key,
                )
            )
            if existing is not None:
                if existing.request_hash != digest:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "IDEMPOTENCY_CONFLICT",
                        "Khóa gửi tin đã được dùng cho nội dung khác.",
                    )
                return
            sequence = (
                int(
                    await self.session.scalar(
                        select(func.coalesce(func.max(ConversationMessage.sequence_no), 0)).where(
                            ConversationMessage.conversation_id == conversation.id
                        )
                    )
                    or 0
                )
                + 1
            )
            message = ConversationMessage(
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                sequence_no=sequence,
                actor="human",
                direction="outbound",
                text=request.text,
                status="completed",
                request_key=key,
                request_hash=digest,
                completed_at=now,
            )
            self.session.add(message)
            await self.session.flush()
            connection = await self.session.get(
                ChannelConnection, conversation.channel_connection_id
            )
            if connection is None or connection.workspace_id != workspace_id:
                raise RuntimeError("Conversation channel connection is missing")
            if connection.provider in {"facebook", "zalo"}:
                thread = await self.session.scalar(
                    select(ChannelThreadMapping).where(
                        ChannelThreadMapping.workspace_id == workspace_id,
                        ChannelThreadMapping.connection_id == connection.id,
                        ChannelThreadMapping.conversation_id == conversation.id,
                    )
                )
                if thread is None:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "THREAD_UNAVAILABLE",
                        "Không tìm thấy luồng gửi của kênh.",
                    )
                self.session.add_all(
                    (
                        ChannelMessageMapping(
                            workspace_id=workspace_id,
                            connection_id=connection.id,
                            thread_mapping_id=thread.id,
                            message_id=message.id,
                            direction="outbound",
                        ),
                        OutboundDelivery(
                            workspace_id=workspace_id,
                            connection_id=connection.id,
                            message_id=message.id,
                            idempotency_key=f"human-reply:{message.id}",
                            next_attempt_at=now,
                        ),
                    )
                )
            conversation.last_message_at = now
            self.session.add(
                ConversationAuditEvent(
                    workspace_id=workspace_id,
                    conversation_id=conversation.id,
                    actor_member_id=member.id,
                    event_type="human_replied",
                    details_json={"message_id": message.id},
                )
            )

    async def dashboard(
        self, user: User, workspace_id: UUID, days: Literal[7, 30]
    ) -> DashboardResponse:
        workspace, member = await self._access(user, workspace_id)
        if member.role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền xem tổng quan.",
            )
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
        recent_rows = await self.repository.list_rows(
            workspace_id, limit=5, member_id=member.id, role=member.role
        )
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
