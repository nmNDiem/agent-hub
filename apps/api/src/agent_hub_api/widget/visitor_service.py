from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from fastapi import status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.agents.runtime import AgentConversationTurn, AgentRuntimeUsage
from agent_hub_api.analytics.events import record_product_impressions
from agent_hub_api.channels.models import ChannelAgentBinding, ChannelConnection
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.leads.schemas import contact_consent_text, contact_consent_version
from agent_hub_api.telemetry.service import TelemetryService
from agent_hub_api.widget.models import (
    VisitorImageUpload,
    WidgetDomain,
    WidgetRateWindow,
    WidgetSession,
)
from agent_hub_api.widget.public_schemas import (
    PublicGroundedResponse,
    WidgetCapabilities,
    WidgetContactConfig,
    WidgetConversationResponse,
    WidgetPublishedConfig,
    WidgetSessionResponse,
    WidgetTranscriptMessage,
    WidgetTranscriptResponse,
)
from agent_hub_api.widget.schemas import normalize_widget_origin
from agent_hub_api.widget.vision import VisionResult


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _request_hash(message: str, attachment_id: UUID | None) -> str:
    payload = json.dumps(
        {
            "message": message,
            "attachment_id": str(attachment_id) if attachment_id is not None else None,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class VisitorContext:
    session_id: int
    workspace_id: UUID
    agent_id: int
    channel_id: int
    revision_id: int
    origin: str
    expires_at: datetime
    revision: AgentRevision


@dataclass(frozen=True, slots=True)
class PreparedTurn:
    context: VisitorContext
    conversation_id: int
    conversation_public_id: UUID
    assistant_message_id: int
    response_id: UUID
    question: str
    history: tuple[AgentConversationTurn, ...]
    attachment: PreparedAttachment | None = None
    replay: PublicGroundedResponse | None = None
    waiting_human: bool = False


@dataclass(frozen=True, slots=True)
class PreparedAttachment:
    upload_id: int
    object_key: str
    content_type: str


@dataclass(frozen=True, slots=True)
class PendingImageCleanup:
    image_id: int
    object_key: str


class WidgetVisitorService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        image_input_enabled: bool = False,
    ) -> None:
        self.session = session
        self.settings = settings
        self.image_input_enabled = image_input_enabled

    def _abuse_key(self) -> bytes:
        value = self.settings.widget_abuse_hash_key
        if value is None or len(value.encode()) < 32:
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "WIDGET_DISABLED",
                "Chatbot hiện chưa sẵn sàng.",
            )
        return value.encode()

    def _rate_key(self, scope: str, value: str) -> str:
        return hmac.new(self._abuse_key(), f"{scope}:{value}".encode(), hashlib.sha256).hexdigest()

    async def _consume_rate(
        self,
        *,
        workspace_id: UUID,
        scope: str,
        value: str,
        window_seconds: int,
        limit: int,
    ) -> None:
        now = datetime.now(UTC)
        started = datetime.fromtimestamp(
            int(now.timestamp()) // window_seconds * window_seconds, UTC
        )
        key_hash = self._rate_key(scope, value)
        bucket = (
            await self.session.scalars(
                select(WidgetRateWindow)
                .where(
                    WidgetRateWindow.workspace_id == workspace_id,
                    WidgetRateWindow.scope == scope,
                    WidgetRateWindow.key_hash == key_hash,
                    WidgetRateWindow.window_started_at == started,
                )
                .with_for_update()
            )
        ).one_or_none()
        if bucket is None:
            bucket = WidgetRateWindow(
                workspace_id=workspace_id,
                scope=scope,
                key_hash=key_hash,
                window_started_at=started,
                count=0,
            )
            self.session.add(bucket)
        if bucket.count >= limit:
            raise ApiError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "RATE_LIMITED",
                "Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.",
            )
        bucket.count += 1

    async def create_session(
        self, *, public_agent_id: UUID, origin: str, client_address: str
    ) -> WidgetSessionResponse:
        try:
            normalized_origin = normalize_widget_origin(origin)
        except ValueError as exc:
            raise ApiError(
                status.HTTP_404_NOT_FOUND,
                "WIDGET_UNAVAILABLE",
                "Chatbot hiện không khả dụng.",
            ) from exc
        async with self.session.begin():
            row = (
                await self.session.execute(
                    select(Agent, ChannelConnection, ChannelAgentBinding, AgentRevision)
                    .join(
                        ChannelAgentBinding,
                        (ChannelAgentBinding.workspace_id == Agent.workspace_id)
                        & (ChannelAgentBinding.agent_id == Agent.id),
                    )
                    .join(
                        ChannelConnection,
                        (ChannelConnection.workspace_id == ChannelAgentBinding.workspace_id)
                        & (ChannelConnection.id == ChannelAgentBinding.connection_id),
                    )
                    .join(
                        AgentRevision,
                        (AgentRevision.workspace_id == ChannelAgentBinding.workspace_id)
                        & (AgentRevision.agent_id == ChannelAgentBinding.agent_id)
                        & (AgentRevision.id == ChannelAgentBinding.active_revision_id),
                    )
                    .where(
                        Agent.public_id == public_agent_id,
                        Agent.archived_at.is_(None),
                        Agent.status == "published",
                        ChannelConnection.provider == "web",
                        ChannelConnection.lifecycle_state == "active",
                        ChannelAgentBinding.enabled.is_(True),
                    )
                )
            ).one_or_none()
            if row is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "WIDGET_UNAVAILABLE",
                    "Chatbot hiện không khả dụng.",
                )
            agent, channel, _, revision = row
            allowed = await self.session.scalar(
                select(WidgetDomain.id).where(
                    WidgetDomain.workspace_id == agent.workspace_id,
                    WidgetDomain.channel_id == channel.id,
                    WidgetDomain.normalized_origin == normalized_origin,
                )
            )
            if allowed is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "WIDGET_UNAVAILABLE",
                    "Chatbot hiện không khả dụng.",
                )
            await self._consume_rate(
                workspace_id=agent.workspace_id,
                scope="bootstrap_ip",
                value=client_address,
                window_seconds=60,
                limit=self.settings.widget_bootstrap_per_ip_minute,
            )
            await self._consume_rate(
                workspace_id=agent.workspace_id,
                scope="sessions_workspace",
                value=str(agent.workspace_id),
                window_seconds=3_600,
                limit=self.settings.widget_sessions_per_workspace_hour,
            )
            raw_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC) + timedelta(hours=self.settings.widget_session_hours)
            self.session.add(
                WidgetSession(
                    workspace_id=agent.workspace_id,
                    agent_id=agent.id,
                    channel_id=channel.id,
                    revision_id=revision.id,
                    token_hash=_token_hash(raw_token),
                    normalized_origin=normalized_origin,
                    expires_at=expires_at,
                )
            )
        widget = revision.widget_config_json
        position = cast(str, widget.get("launcher_position", "right"))
        return WidgetSessionResponse(
            access_token=raw_token,
            expires_at=expires_at,
            config=WidgetPublishedConfig(
                display_name=revision.name,
                greeting=revision.greeting,
                brand_color=cast(str, widget.get("brand_color", "#0F8F87")),
                launcher_position="left" if position == "left" else "right",
                capabilities=WidgetCapabilities(image_input=self.image_input_enabled),
                contact=WidgetContactConfig(
                    handoff_url=cast(str | None, widget.get("handoff_url")),
                    handoff_label=cast(str | None, widget.get("handoff_label")),
                    consent_text=contact_consent_text(self.settings.lead_retention_days),
                    consent_text_version=contact_consent_version(self.settings.lead_retention_days),
                    lead_retention_days=self.settings.lead_retention_days,
                ),
            ),
        )

    async def resolve_context(self, *, token: str, origin: str) -> VisitorContext:
        try:
            normalized_origin = normalize_widget_origin(origin)
        except ValueError as exc:
            raise ApiError(
                status.HTTP_401_UNAUTHORIZED,
                "INVALID_WIDGET_SESSION",
                "Phiên chat không hợp lệ.",
            ) from exc
        row = (
            await self.session.execute(
                select(
                    WidgetSession,
                    ChannelConnection,
                    ChannelAgentBinding,
                    AgentRevision,
                    Agent,
                )
                .join(
                    ChannelConnection,
                    (ChannelConnection.workspace_id == WidgetSession.workspace_id)
                    & (ChannelConnection.id == WidgetSession.channel_id),
                )
                .join(
                    ChannelAgentBinding,
                    (ChannelAgentBinding.workspace_id == WidgetSession.workspace_id)
                    & (ChannelAgentBinding.connection_id == WidgetSession.channel_id)
                    & (ChannelAgentBinding.agent_id == WidgetSession.agent_id),
                )
                .join(
                    AgentRevision,
                    (AgentRevision.workspace_id == WidgetSession.workspace_id)
                    & (AgentRevision.agent_id == WidgetSession.agent_id)
                    & (AgentRevision.id == WidgetSession.revision_id),
                )
                .join(
                    Agent,
                    (Agent.workspace_id == WidgetSession.workspace_id)
                    & (Agent.id == WidgetSession.agent_id),
                )
                .where(WidgetSession.token_hash == _token_hash(token))
            )
        ).one_or_none()
        if row is None:
            raise ApiError(
                status.HTTP_401_UNAUTHORIZED,
                "INVALID_WIDGET_SESSION",
                "Phiên chat không hợp lệ.",
            )
        widget_session, channel, binding, revision, agent = row
        now = datetime.now(UTC)
        if (
            widget_session.revoked_at is not None
            or _aware(widget_session.expires_at) <= now
            or widget_session.normalized_origin != normalized_origin
            or channel.provider != "web"
            or channel.lifecycle_state != "active"
            or not binding.enabled
            or agent.status != "published"
            or agent.archived_at is not None
        ):
            raise ApiError(
                status.HTTP_401_UNAUTHORIZED,
                "INVALID_WIDGET_SESSION",
                "Phiên chat đã hết hạn hoặc bị thu hồi.",
            )
        allowed = await self.session.scalar(
            select(WidgetDomain.id).where(
                WidgetDomain.workspace_id == widget_session.workspace_id,
                WidgetDomain.channel_id == widget_session.channel_id,
                WidgetDomain.normalized_origin == normalized_origin,
            )
        )
        if allowed is None:
            raise ApiError(
                status.HTTP_401_UNAUTHORIZED,
                "INVALID_WIDGET_SESSION",
                "Phiên chat đã bị thu hồi.",
            )
        return VisitorContext(
            session_id=widget_session.id,
            workspace_id=widget_session.workspace_id,
            agent_id=widget_session.agent_id,
            channel_id=widget_session.channel_id,
            revision_id=widget_session.revision_id,
            origin=normalized_origin,
            expires_at=_aware(widget_session.expires_at),
            revision=revision,
        )

    async def create_conversation(self, *, token: str, origin: str) -> WidgetConversationResponse:
        async with self.session.begin():
            context = await self.resolve_context(token=token, origin=origin)
            conversation = (
                await self.session.scalars(
                    select(Conversation).where(Conversation.session_id == context.session_id)
                )
            ).one_or_none()
            if conversation is None:
                retention_until = min(
                    context.expires_at,
                    datetime.now(UTC) + timedelta(hours=self.settings.widget_transcript_hours),
                )
                conversation = Conversation(
                    public_id=new_uuid_v7(),
                    workspace_id=context.workspace_id,
                    agent_id=context.agent_id,
                    revision_id=context.revision_id,
                    channel_connection_id=context.channel_id,
                    session_id=context.session_id,
                    retention_until=retention_until,
                )
                self.session.add(conversation)
                await self.session.flush()
        return self._conversation_response(conversation)

    async def transcript(
        self, *, token: str, origin: str, public_id: UUID
    ) -> WidgetTranscriptResponse:
        context = await self.resolve_context(token=token, origin=origin)
        conversation = await self._conversation(context, public_id)
        rows = list(
            await self.session.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.workspace_id == context.workspace_id,
                    ConversationMessage.conversation_id == conversation.id,
                )
                .order_by(ConversationMessage.sequence_no)
            )
        )
        items: list[WidgetTranscriptMessage] = []
        for row in rows:
            response = self._stored_response(row)
            items.append(
                WidgetTranscriptMessage(
                    sequence_no=row.sequence_no,
                    role="user" if row.actor == "visitor" else "assistant",
                    text=row.text,
                    status=cast(
                        Literal["pending", "completed", "failed", "cancelled"],
                        row.status,
                    ),
                    response_id=row.response_id,
                    product_cards=response.product_cards if response else [],
                    sources=response.sources if response else [],
                    created_at=row.created_at,
                )
            )
        return WidgetTranscriptResponse(
            items=items,
            waiting_human=conversation.handling_mode != "ai",
        )

    async def prepare_turn(
        self,
        *,
        token: str,
        origin: str,
        conversation_public_id: UUID,
        request_key: str,
        question: str,
        attachment_id: UUID | None = None,
    ) -> PreparedTurn:
        request_digest = _request_hash(question, attachment_id)
        async with self.session.begin():
            context = await self.resolve_context(token=token, origin=origin)
            conversation = await self._conversation(
                context, conversation_public_id, for_update=True
            )
            existing = (
                await self.session.scalars(
                    select(ConversationMessage).where(
                        ConversationMessage.conversation_id == conversation.id,
                        ConversationMessage.request_key == request_key,
                    )
                )
            ).one_or_none()
            if existing is not None:
                if existing.request_hash != request_digest:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "IDEMPOTENCY_CONFLICT",
                        "Khóa gửi tin đã được dùng cho nội dung khác.",
                    )
                if conversation.handling_mode != "ai":
                    return PreparedTurn(
                        context=context,
                        conversation_id=conversation.id,
                        conversation_public_id=conversation.public_id,
                        assistant_message_id=0,
                        response_id=new_uuid_v7(),
                        question=question,
                        history=(),
                        waiting_human=True,
                    )
                assistant = await self._assistant_after(existing)
                if assistant.status != "completed":
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "TURN_NOT_REPLAYABLE",
                        "Lượt chat này chưa có kết quả hoàn tất.",
                    )
                replay = self._stored_response(assistant)
                if replay is None or assistant.response_id is None:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "TURN_NOT_REPLAYABLE",
                        "Không thể phát lại lượt chat này.",
                    )
                return PreparedTurn(
                    context=context,
                    conversation_id=conversation.id,
                    conversation_public_id=conversation.public_id,
                    assistant_message_id=assistant.id,
                    response_id=assistant.response_id,
                    question=question,
                    history=(),
                    replay=replay,
                )

            pending = (
                await self.session.scalars(
                    select(ConversationMessage).where(
                        ConversationMessage.conversation_id == conversation.id,
                        ConversationMessage.actor == "assistant",
                        ConversationMessage.status == "pending",
                    )
                )
            ).one_or_none()
            now = datetime.now(UTC)
            if pending is not None:
                deadline = pending.generation_deadline
                if deadline is not None and _aware(deadline) <= now:
                    pending.status = "failed"
                    pending.safe_error_code = "TURN_EXPIRED"
                    pending.completed_at = now
                else:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "TURN_IN_PROGRESS",
                        "Một phản hồi khác đang được xử lý.",
                    )
            await self._consume_rate(
                workspace_id=context.workspace_id,
                scope="messages_session",
                value=str(context.session_id),
                window_seconds=3_600,
                limit=self.settings.widget_messages_per_session_hour,
            )
            await self._consume_rate(
                workspace_id=context.workspace_id,
                scope="messages_workspace",
                value=str(context.workspace_id),
                window_seconds=3_600,
                limit=self.settings.widget_messages_per_workspace_hour,
            )
            history = await self._history(conversation.id)
            attachment: PreparedAttachment | None = None
            if attachment_id is not None:
                if not self.image_input_enabled:
                    raise ApiError(
                        status.HTTP_503_SERVICE_UNAVAILABLE,
                        "IMAGE_INPUT_DISABLED",
                        "Chatbot hiện chưa hỗ trợ nhận ảnh.",
                    )
                upload = (
                    await self.session.scalars(
                        select(VisitorImageUpload)
                        .where(
                            VisitorImageUpload.workspace_id == context.workspace_id,
                            VisitorImageUpload.session_id == context.session_id,
                            VisitorImageUpload.public_id == attachment_id,
                            VisitorImageUpload.status == "available",
                            VisitorImageUpload.expires_at > now,
                        )
                        .with_for_update()
                    )
                ).one_or_none()
                if upload is None or upload.object_key is None:
                    raise ApiError(
                        status.HTTP_404_NOT_FOUND,
                        "ATTACHMENT_NOT_FOUND",
                        "Không tìm thấy ảnh đính kèm.",
                    )
                upload.status = "attached"
                upload.attached_conversation_id = conversation.id
                upload.attached_request_key = request_key
                upload.expires_at = now + timedelta(hours=self.settings.widget_image_attached_hours)
                upload.updated_at = now
                attachment = PreparedAttachment(
                    upload_id=upload.id,
                    object_key=upload.object_key,
                    content_type=upload.content_type,
                )
            last_sequence = await self.session.scalar(
                select(func.max(ConversationMessage.sequence_no)).where(
                    ConversationMessage.conversation_id == conversation.id
                )
            )
            visitor_sequence = int(last_sequence or 0) + 1
            if conversation.handling_mode != "ai":
                self.session.add(
                    ConversationMessage(
                        workspace_id=context.workspace_id,
                        conversation_id=conversation.id,
                        sequence_no=visitor_sequence,
                        actor="visitor",
                        direction="inbound",
                        text=question,
                        status="completed",
                        request_key=request_key,
                        request_hash=request_digest,
                        completed_at=now,
                    )
                )
                conversation.last_message_at = now
                return PreparedTurn(
                    context=context,
                    conversation_id=conversation.id,
                    conversation_public_id=conversation.public_id,
                    assistant_message_id=0,
                    response_id=new_uuid_v7(),
                    question=question,
                    history=history,
                    attachment=attachment,
                    waiting_human=True,
                )
            await TelemetryService(self.session, self.settings).reserve_generation_turn(
                context.workspace_id, context.agent_id
            )
            response_id = new_uuid_v7()
            self.session.add(
                ConversationMessage(
                    workspace_id=context.workspace_id,
                    conversation_id=conversation.id,
                    sequence_no=visitor_sequence,
                    actor="visitor",
                    direction="inbound",
                    text=question,
                    status="completed",
                    request_key=request_key,
                    request_hash=request_digest,
                    completed_at=now,
                )
            )
            assistant = ConversationMessage(
                workspace_id=context.workspace_id,
                conversation_id=conversation.id,
                sequence_no=visitor_sequence + 1,
                actor="assistant",
                direction="outbound",
                text="",
                status="pending",
                response_id=response_id,
                generation_deadline=now
                + timedelta(seconds=self.settings.openai_timeout_seconds + 30),
            )
            self.session.add(assistant)
            conversation.last_message_at = now
            await self.session.flush()
        return PreparedTurn(
            context=context,
            conversation_id=conversation.id,
            conversation_public_id=conversation.public_id,
            assistant_message_id=assistant.id,
            response_id=response_id,
            question=question,
            history=history,
            attachment=attachment,
        )

    async def record_attachment_analysis(
        self,
        turn: PreparedTurn,
        *,
        analysis: dict[str, object],
    ) -> None:
        if turn.attachment is None:
            return
        async with self.session.begin():
            upload = (
                await self.session.scalars(
                    select(VisitorImageUpload)
                    .where(
                        VisitorImageUpload.id == turn.attachment.upload_id,
                        VisitorImageUpload.workspace_id == turn.context.workspace_id,
                        VisitorImageUpload.session_id == turn.context.session_id,
                        VisitorImageUpload.attached_conversation_id == turn.conversation_id,
                        VisitorImageUpload.status == "attached",
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if upload is None:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "ATTACHMENT_STATE_CHANGED",
                    "Ảnh đính kèm đã thay đổi trạng thái.",
                )
            upload.analysis_json = analysis
            upload.updated_at = datetime.now(UTC)

    async def complete_turn(
        self,
        turn: PreparedTurn,
        *,
        token: str,
        origin: str,
        response: PublicGroundedResponse,
        product_ids: tuple[int, ...] = (),
        generation_usage: AgentRuntimeUsage | None = None,
        vision_result: VisionResult | None = None,
    ) -> bool:
        async with self.session.begin():
            context = await self.resolve_context(token=token, origin=origin)
            if context.session_id != turn.context.session_id:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy lượt chat.")
            conversation = await self.session.get(
                Conversation, turn.conversation_id, with_for_update=True
            )
            if conversation is None or conversation.workspace_id != context.workspace_id:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy lượt chat.")
            assistant = await self.session.get(ConversationMessage, turn.assistant_message_id)
            if assistant is None or assistant.status != "pending":
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "TURN_STATE_CHANGED",
                    "Lượt chat đã thay đổi trạng thái.",
                )
            if conversation.handling_mode != "ai":
                assistant.status = "cancelled"
                assistant.safe_error_code = "HUMAN_TAKEOVER"
                assistant.completed_at = datetime.now(UTC)
                assistant.generation_deadline = None
                if generation_usage is not None:
                    TelemetryService(self.session, self.settings).record_generation(
                        workspace_id=context.workspace_id,
                        agent_id=context.agent_id,
                        conversation_id=turn.conversation_id,
                        surface="widget",
                        usage=generation_usage,
                    )
                if vision_result is not None:
                    TelemetryService(self.session, self.settings).record_vision(
                        workspace_id=context.workspace_id,
                        agent_id=context.agent_id,
                        conversation_id=turn.conversation_id,
                        result=vision_result,
                    )
                return False
            assistant.text = response.text
            assistant.response_json = response.model_dump(mode="json")
            assistant.status = "completed"
            assistant.input_tokens = response.usage.get("input_tokens", 0)
            assistant.output_tokens = response.usage.get("output_tokens", 0)
            assistant.total_tokens = response.usage.get("total_tokens", 0)
            assistant.completed_at = datetime.now(UTC)
            assistant.generation_deadline = None
            record_product_impressions(
                self.session,
                workspace_id=context.workspace_id,
                agent_id=context.agent_id,
                conversation_id=turn.conversation_id,
                message_id=assistant.id,
                channel="web",
                product_ids=product_ids,
                occurred_at=assistant.completed_at,
            )
            telemetry = TelemetryService(self.session, self.settings)
            if generation_usage is not None:
                telemetry.record_generation(
                    workspace_id=context.workspace_id,
                    agent_id=context.agent_id,
                    conversation_id=turn.conversation_id,
                    surface="widget",
                    usage=generation_usage,
                )
            if vision_result is not None:
                telemetry.record_vision(
                    workspace_id=context.workspace_id,
                    agent_id=context.agent_id,
                    conversation_id=turn.conversation_id,
                    result=vision_result,
                )
        return True

    async def cancel_turn(self, turn: PreparedTurn, *, code: str) -> None:
        async with self.session.begin():
            await self.session.execute(
                update(ConversationMessage)
                .where(
                    ConversationMessage.id == turn.assistant_message_id,
                    ConversationMessage.status == "pending",
                )
                .values(
                    status="cancelled",
                    safe_error_code=code,
                    completed_at=datetime.now(UTC),
                    generation_deadline=None,
                )
            )

    async def replay_turn(
        self,
        *,
        token: str,
        origin: str,
        conversation_public_id: UUID,
        request_key: str,
    ) -> PreparedTurn:
        context = await self.resolve_context(token=token, origin=origin)
        conversation = await self._conversation(context, conversation_public_id)
        visitor = (
            await self.session.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.request_key == request_key,
                )
            )
        ).one_or_none()
        if visitor is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy lượt chat.")
        assistant = await self._assistant_after(visitor)
        response = self._stored_response(assistant)
        if assistant.status != "completed" or response is None or assistant.response_id is None:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "TURN_NOT_REPLAYABLE",
                "Lượt chat này chưa có kết quả để phát lại.",
            )
        return PreparedTurn(
            context=context,
            conversation_id=conversation.id,
            conversation_public_id=conversation.public_id,
            assistant_message_id=assistant.id,
            response_id=assistant.response_id,
            question=visitor.text,
            history=(),
            replay=response,
        )

    async def delete_conversation(
        self, *, token: str, origin: str, conversation_public_id: UUID
    ) -> tuple[PendingImageCleanup, ...]:
        now = datetime.now(UTC)
        async with self.session.begin():
            context = await self.resolve_context(token=token, origin=origin)
            conversation = await self._conversation(
                context, conversation_public_id, for_update=True
            )
            uploads = list(
                await self.session.scalars(
                    select(VisitorImageUpload)
                    .where(
                        VisitorImageUpload.workspace_id == context.workspace_id,
                        VisitorImageUpload.session_id == context.session_id,
                    )
                    .with_for_update()
                )
            )
            conversation.lifecycle_state = "deleted"
            await self.session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.conversation_id == conversation.id
                )
            )
            await self.session.execute(
                update(WidgetSession)
                .where(WidgetSession.id == context.session_id)
                .values(revoked_at=now)
            )
            pending: list[PendingImageCleanup] = []
            for upload in uploads:
                upload.analysis_json = None
                upload.updated_at = now
                upload.last_cleanup_error = None
                if upload.object_key is None:
                    await self.session.delete(upload)
                    continue
                upload.status = "cleanup_pending"
                pending.append(
                    PendingImageCleanup(image_id=upload.id, object_key=upload.object_key)
                )
        return tuple(pending)

    async def finish_image_cleanup(
        self,
        pending: PendingImageCleanup,
        *,
        error_code: str | None = None,
    ) -> None:
        async with self.session.begin():
            if error_code is None:
                await self.session.execute(
                    delete(VisitorImageUpload).where(
                        VisitorImageUpload.id == pending.image_id,
                        VisitorImageUpload.status == "cleanup_pending",
                        VisitorImageUpload.object_key == pending.object_key,
                    )
                )
                return
            await self.session.execute(
                update(VisitorImageUpload)
                .where(
                    VisitorImageUpload.id == pending.image_id,
                    VisitorImageUpload.status == "cleanup_pending",
                    VisitorImageUpload.object_key == pending.object_key,
                )
                .values(
                    cleanup_attempts=VisitorImageUpload.cleanup_attempts + 1,
                    last_cleanup_error=error_code,
                    updated_at=datetime.now(UTC),
                )
            )

    async def _conversation(
        self, context: VisitorContext, public_id: UUID, *, for_update: bool = False
    ) -> Conversation:
        statement = select(Conversation).where(
            Conversation.workspace_id == context.workspace_id,
            Conversation.public_id == public_id,
            Conversation.session_id == context.session_id,
            Conversation.lifecycle_state == "active",
        )
        if for_update:
            statement = statement.with_for_update()
        conversation = (await self.session.scalars(statement)).one_or_none()
        if conversation is None:
            raise ApiError(
                status.HTTP_404_NOT_FOUND,
                "NOT_FOUND",
                "Không tìm thấy cuộc trò chuyện.",
            )
        return conversation

    async def _assistant_after(self, visitor: ConversationMessage) -> ConversationMessage:
        assistant = (
            await self.session.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.conversation_id == visitor.conversation_id,
                    ConversationMessage.sequence_no == visitor.sequence_no + 1,
                    ConversationMessage.actor == "assistant",
                )
            )
        ).one_or_none()
        if assistant is None:
            raise ApiError(status.HTTP_409_CONFLICT, "TURN_INCOMPLETE", "Lượt chat chưa hoàn tất.")
        return assistant

    async def _history(self, conversation_id: int) -> tuple[AgentConversationTurn, ...]:
        rows = list(
            await self.session.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.status == "completed",
                    ConversationMessage.text != "",
                )
                .order_by(ConversationMessage.sequence_no.desc())
                .limit(self.settings.agent_runtime_max_history_turns)
            )
        )
        return tuple(
            AgentConversationTurn(
                role="user" if row.actor == "visitor" else "assistant",
                content=row.text,
            )
            for row in reversed(rows)
        )

    @staticmethod
    def _stored_response(message: ConversationMessage) -> PublicGroundedResponse | None:
        if message.response_json is None:
            return None
        return PublicGroundedResponse.model_validate(message.response_json)

    @staticmethod
    def _conversation_response(conversation: Conversation) -> WidgetConversationResponse:
        return WidgetConversationResponse(
            public_id=conversation.public_id,
            status="open" if conversation.lifecycle_state == "active" else "deleted",
            retention_until=conversation.retention_until,
        )
