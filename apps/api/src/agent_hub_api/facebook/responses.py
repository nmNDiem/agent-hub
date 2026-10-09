from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import AgentRevision
from agent_hub_api.agents.runtime import (
    AgentConversationTurn,
    AgentExecutionContext,
    AgentRuntimeError,
    AgentRuntimeUsage,
    GroundedAgentResponse,
)
from agent_hub_api.channels.contracts import (
    ChannelCapabilities,
    NormalizedOutboundMessage,
)
from agent_hub_api.channels.models import (
    ChannelAgentBinding,
    ChannelConnection,
    ChannelInboundMedia,
    ChannelMessageMapping,
    ChannelResponseJob,
    ChannelThreadMapping,
    OutboundDelivery,
)
from agent_hub_api.channels.rendering import CapabilityAwareRenderer, ChannelRenderError
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.facebook.media import FacebookMediaDownloader, FacebookMediaError
from agent_hub_api.telemetry.service import TelemetryService
from agent_hub_api.widget.execution import resolve_revision_execution_context
from agent_hub_api.widget.image_storage import (
    VisitorImageStorage,
    VisitorImageStorageError,
)
from agent_hub_api.widget.vision import (
    VisionGateway,
    VisionPermanentError,
    VisionResult,
    VisionTemporaryError,
)


class FacebookResponseError(RuntimeError):
    def __init__(self, safe_code: str, *, retryable: bool) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ClaimedResponseJob:
    id: int
    workspace_id: UUID
    connection_id: int
    conversation_id: int
    inbound_message_id: int
    revision_id: int
    agent_id: int
    thread_mapping_id: int
    lease_token: str
    question: str
    history: tuple[AgentConversationTurn, ...]
    media_ids: tuple[int, ...]


class FacebookRuntime(Protocol):
    async def run_with_context(
        self,
        context: AgentExecutionContext,
        *,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse: ...


FacebookRuntimeFactory = Callable[[AsyncSession], FacebookRuntime]


class FacebookResponseService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def claim(self, *, now: datetime | None = None) -> ClaimedResponseJob | None:
        claimed_at = now or datetime.now(UTC)
        async with self.session.begin():
            await self.session.execute(
                update(ChannelResponseJob)
                .where(
                    ChannelResponseJob.state == "running",
                    ChannelResponseJob.attempt_count >= ChannelResponseJob.max_attempts,
                    ChannelResponseJob.lease_expires_at <= claimed_at,
                )
                .values(
                    state="failed_terminal",
                    safe_error_code="RESPONSE_LEASE_EXPIRED",
                    lease_token=None,
                    lease_expires_at=None,
                    updated_at=claimed_at,
                )
            )
            job = (
                await self.session.scalars(
                    select(ChannelResponseJob)
                    .where(
                        ChannelResponseJob.attempt_count < ChannelResponseJob.max_attempts,
                        or_(
                            and_(
                                ChannelResponseJob.state.in_(("queued", "failed_retryable")),
                                ChannelResponseJob.next_attempt_at <= claimed_at,
                            ),
                            and_(
                                ChannelResponseJob.state == "running",
                                ChannelResponseJob.lease_expires_at <= claimed_at,
                            ),
                        ),
                    )
                    .order_by(ChannelResponseJob.next_attempt_at, ChannelResponseJob.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).one_or_none()
            if job is None:
                return None
            row = (
                await self.session.execute(
                    select(
                        ChannelConnection,
                        Conversation,
                        ConversationMessage,
                        ChannelThreadMapping,
                        ChannelAgentBinding,
                    )
                    .select_from(ChannelResponseJob)
                    .join(
                        Conversation,
                        (Conversation.workspace_id == ChannelResponseJob.workspace_id)
                        & (Conversation.id == ChannelResponseJob.conversation_id),
                    )
                    .join(
                        ConversationMessage,
                        (ConversationMessage.workspace_id == ChannelResponseJob.workspace_id)
                        & (ConversationMessage.id == ChannelResponseJob.inbound_message_id),
                    )
                    .join(
                        ChannelConnection,
                        (ChannelConnection.workspace_id == ChannelResponseJob.workspace_id)
                        & (ChannelConnection.id == ChannelResponseJob.connection_id),
                    )
                    .join(
                        ChannelThreadMapping,
                        (ChannelThreadMapping.workspace_id == ChannelResponseJob.workspace_id)
                        & (ChannelThreadMapping.connection_id == ChannelResponseJob.connection_id)
                        & (
                            ChannelThreadMapping.conversation_id
                            == ChannelResponseJob.conversation_id
                        ),
                    )
                    .join(
                        ChannelAgentBinding,
                        (ChannelAgentBinding.workspace_id == ChannelResponseJob.workspace_id)
                        & (ChannelAgentBinding.connection_id == ChannelResponseJob.connection_id),
                    )
                    .where(ChannelResponseJob.id == job.id)
                    .with_for_update()
                )
            ).one_or_none()
            if row is None:
                self._terminal(job, "RESPONSE_CONTEXT_MISSING", claimed_at)
                return None
            connection, conversation, inbound, thread, binding = row
            window_start = claimed_at - timedelta(
                hours=self.settings.facebook_response_window_hours
            )
            if (
                connection.lifecycle_state != "active"
                or connection.health_state != "healthy"
                or not binding.enabled
                or binding.active_revision_id is None
            ):
                self._terminal(job, "FACEBOOK_REAUTH_REQUIRED", claimed_at)
                return None
            if conversation.handling_mode != "ai" or thread.automation_state != "opted_in":
                job.state = "suppressed"
                job.safe_error_code = "AUTOMATION_SUPPRESSED"
                job.updated_at = claimed_at
                return None
            if thread.last_inbound_at is None or self._aware(thread.last_inbound_at) < window_start:
                self._terminal(job, "FACEBOOK_RESPONSE_WINDOW_EXPIRED", claimed_at)
                return None
            try:
                await TelemetryService(self.session, self.settings).reserve_generation_turn(
                    job.workspace_id, binding.agent_id
                )
            except ApiError as exc:
                self._terminal(job, exc.code, claimed_at)
                return None

            history_rows = list(
                await self.session.scalars(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.workspace_id == job.workspace_id,
                        ConversationMessage.conversation_id == job.conversation_id,
                        ConversationMessage.id != inbound.id,
                        ConversationMessage.status == "completed",
                        ConversationMessage.actor.in_(("visitor", "assistant")),
                    )
                    .order_by(ConversationMessage.sequence_no.desc())
                    .limit(self.settings.agent_runtime_max_history_turns)
                )
            )
            history = tuple(
                AgentConversationTurn(
                    role="user" if item.actor == "visitor" else "assistant",
                    content=item.text,
                )
                for item in reversed(history_rows)
                if item.text.strip()
            )
            media_ids = tuple(
                await self.session.scalars(
                    select(ChannelInboundMedia.id).where(
                        ChannelInboundMedia.workspace_id == job.workspace_id,
                        ChannelInboundMedia.message_id == inbound.id,
                        ChannelInboundMedia.kind == "image",
                        ChannelInboundMedia.state == "pending",
                    )
                )
            )
            token = secrets.token_hex(32)
            job.state = "running"
            job.attempt_count += 1
            job.lease_token = token
            job.lease_expires_at = claimed_at + timedelta(
                seconds=self.settings.facebook_response_job_lease_seconds
            )
            job.safe_error_code = None
            job.updated_at = claimed_at
            return ClaimedResponseJob(
                id=job.id,
                workspace_id=job.workspace_id,
                connection_id=job.connection_id,
                conversation_id=job.conversation_id,
                inbound_message_id=job.inbound_message_id,
                revision_id=binding.active_revision_id,
                agent_id=binding.agent_id,
                thread_mapping_id=thread.id,
                lease_token=token,
                question=inbound.text,
                history=history,
                media_ids=media_ids,
            )

    async def complete(
        self,
        claim: ClaimedResponseJob,
        *,
        text: str,
        response_json: dict[str, object],
        usage: AgentRuntimeUsage,
        vision_results: tuple[VisionResult, ...] = (),
    ) -> None:
        completed_at = datetime.now(UTC)
        async with self.session.begin():
            job = await self._locked_claim(claim)
            thread = (
                await self.session.scalars(
                    select(ChannelThreadMapping)
                    .where(
                        ChannelThreadMapping.workspace_id == claim.workspace_id,
                        ChannelThreadMapping.id == claim.thread_mapping_id,
                        ChannelThreadMapping.connection_id == claim.connection_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if thread is None:
                raise FacebookResponseError("RESPONSE_CONTEXT_MISSING", retryable=False)
            window_start = completed_at - timedelta(
                hours=self.settings.facebook_response_window_hours
            )
            if (
                thread.automation_state != "opted_in"
                or thread.last_inbound_at is None
                or self._aware(thread.last_inbound_at) < window_start
            ):
                job.state = "suppressed"
                job.safe_error_code = "FACEBOOK_RESPONSE_WINDOW_EXPIRED"
                job.lease_token = None
                job.lease_expires_at = None
                job.updated_at = completed_at
                return
            last_sequence = await self.session.scalar(
                select(ConversationMessage.sequence_no)
                .where(ConversationMessage.conversation_id == claim.conversation_id)
                .order_by(ConversationMessage.sequence_no.desc())
                .limit(1)
            )
            assistant = ConversationMessage(
                workspace_id=claim.workspace_id,
                conversation_id=claim.conversation_id,
                sequence_no=int(last_sequence or 0) + 1,
                actor="assistant",
                direction="outbound",
                text=text,
                response_json=response_json,
                status="completed",
                input_tokens=int(getattr(usage, "input_tokens", 0)),
                output_tokens=int(getattr(usage, "output_tokens", 0)),
                total_tokens=int(getattr(usage, "total_tokens", 0)),
                completed_at=completed_at,
            )
            self.session.add(assistant)
            await self.session.flush()
            self.session.add_all(
                (
                    ChannelMessageMapping(
                        workspace_id=claim.workspace_id,
                        connection_id=claim.connection_id,
                        thread_mapping_id=claim.thread_mapping_id,
                        message_id=assistant.id,
                        direction="outbound",
                    ),
                    OutboundDelivery(
                        workspace_id=claim.workspace_id,
                        connection_id=claim.connection_id,
                        message_id=assistant.id,
                        idempotency_key=f"facebook-response:{job.id}",
                        next_attempt_at=completed_at,
                    ),
                )
            )
            conversation = await self.session.get(Conversation, claim.conversation_id)
            if conversation is not None:
                conversation.last_message_at = completed_at
            job.outbound_message_id = assistant.id
            job.state = "completed"
            job.lease_token = None
            job.lease_expires_at = None
            job.safe_error_code = None
            job.updated_at = completed_at
            TelemetryService(self.session, self.settings).record_generation(
                workspace_id=claim.workspace_id,
                agent_id=claim.agent_id,
                conversation_id=claim.conversation_id,
                surface="facebook",
                usage=usage,
            )
            for result in vision_results:
                TelemetryService(self.session, self.settings).record_vision(
                    workspace_id=claim.workspace_id,
                    agent_id=claim.agent_id,
                    conversation_id=claim.conversation_id,
                    result=result,
                    surface="facebook",
                )

    async def fail(self, claim: ClaimedResponseJob, *, safe_code: str, retryable: bool) -> None:
        failed_at = datetime.now(UTC)
        async with self.session.begin():
            job = await self._locked_claim(claim)
            can_retry = retryable and job.attempt_count < job.max_attempts
            job.state = "failed_retryable" if can_retry else "failed_terminal"
            job.safe_error_code = safe_code
            job.next_attempt_at = failed_at + timedelta(
                seconds=min(300, 2 ** max(job.attempt_count, 1))
            )
            job.lease_token = None
            job.lease_expires_at = None
            job.updated_at = failed_at

    async def media_source(self, claim: ClaimedResponseJob, media_id: int) -> str:
        now = datetime.now(UTC)
        async with self.session.begin():
            media = (
                await self.session.scalars(
                    select(ChannelInboundMedia)
                    .where(
                        ChannelInboundMedia.id == media_id,
                        ChannelInboundMedia.workspace_id == claim.workspace_id,
                        ChannelInboundMedia.connection_id == claim.connection_id,
                        ChannelInboundMedia.message_id == claim.inbound_message_id,
                        ChannelInboundMedia.state == "pending",
                        ChannelInboundMedia.expires_at > now,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if media is None or media.source_url is None:
                raise FacebookResponseError("FACEBOOK_MEDIA_MISSING", retryable=False)
            return media.source_url

    async def mark_media_uploading(
        self, claim: ClaimedResponseJob, media_id: int, object_key: str
    ) -> None:
        async with self.session.begin():
            media = await self._locked_media(claim, media_id)
            media.object_key = object_key
            media.state = "cleanup_pending"
            media.updated_at = datetime.now(UTC)

    async def complete_media(
        self,
        claim: ClaimedResponseJob,
        media_id: int,
        *,
        content_type: str,
        content: bytes,
        width: int,
        height: int,
    ) -> None:
        async with self.session.begin():
            media = await self._locked_media(claim, media_id)
            media.source_url = None
            media.content_type = content_type
            media.byte_size = len(content)
            media.width = width
            media.height = height
            media.sha256 = hashlib.sha256(content).hexdigest()
            media.state = "available"
            media.safe_error_code = None
            media.updated_at = datetime.now(UTC)

    async def fail_media(self, claim: ClaimedResponseJob, media_id: int, safe_code: str) -> None:
        async with self.session.begin():
            media = await self._locked_media(claim, media_id)
            media.source_url = None
            media.state = "cleanup_pending" if media.object_key else "failed"
            media.safe_error_code = safe_code
            media.updated_at = datetime.now(UTC)

    async def cleanup_once(self, storage: VisitorImageStorage) -> bool:
        now = datetime.now(UTC)
        async with self.session.begin():
            media = (
                await self.session.scalars(
                    select(ChannelInboundMedia)
                    .where(
                        or_(
                            ChannelInboundMedia.state == "cleanup_pending",
                            and_(
                                ChannelInboundMedia.state.in_(("pending", "available", "failed")),
                                ChannelInboundMedia.expires_at <= now,
                            ),
                        )
                    )
                    .order_by(ChannelInboundMedia.expires_at, ChannelInboundMedia.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).one_or_none()
            if media is None:
                return False
            media.state = "cleanup_pending"
            media.source_url = None
            media_id = media.id
            object_key = media.object_key
        if object_key is not None:
            try:
                await storage.delete(object_key=object_key)
            except VisitorImageStorageError:
                return True
        async with self.session.begin():
            media = await self.session.get(ChannelInboundMedia, media_id)
            if media is not None and media.state == "cleanup_pending":
                media.state = "deleted"
                media.object_key = None
                media.updated_at = datetime.now(UTC)
        return True

    async def _locked_claim(self, claim: ClaimedResponseJob) -> ChannelResponseJob:
        job = (
            await self.session.scalars(
                select(ChannelResponseJob)
                .where(
                    ChannelResponseJob.id == claim.id,
                    ChannelResponseJob.workspace_id == claim.workspace_id,
                    ChannelResponseJob.state == "running",
                    ChannelResponseJob.lease_token == claim.lease_token,
                )
                .with_for_update()
            )
        ).one_or_none()
        if job is None:
            raise FacebookResponseError("STALE_RESPONSE_LEASE", retryable=False)
        return job

    async def _locked_media(self, claim: ClaimedResponseJob, media_id: int) -> ChannelInboundMedia:
        media = (
            await self.session.scalars(
                select(ChannelInboundMedia)
                .where(
                    ChannelInboundMedia.id == media_id,
                    ChannelInboundMedia.workspace_id == claim.workspace_id,
                    ChannelInboundMedia.message_id == claim.inbound_message_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if media is None:
            raise FacebookResponseError("FACEBOOK_MEDIA_MISSING", retryable=False)
        return media

    @staticmethod
    def _terminal(job: ChannelResponseJob, code: str, now: datetime) -> None:
        job.state = "failed_terminal"
        job.safe_error_code = code
        job.lease_token = None
        job.lease_expires_at = None
        job.updated_at = now

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class FacebookResponseRunner:
    def __init__(
        self,
        service: FacebookResponseService,
        *,
        runtime_factory: FacebookRuntimeFactory,
        media_downloader: FacebookMediaDownloader,
        storage: VisitorImageStorage,
        vision: VisionGateway | None,
    ) -> None:
        self.service = service
        self.runtime_factory = runtime_factory
        self.media_downloader = media_downloader
        self.storage = storage
        self.vision = vision
        self.renderer = CapabilityAwareRenderer(
            provider="facebook",
            capabilities=ChannelCapabilities(text=True),
            max_text_characters=2_000,
        )

    async def run_once(self) -> bool:
        claim = await self.service.claim()
        if claim is None:
            return False
        try:
            question_parts = [claim.question.strip()] if claim.question.strip() else []
            vision_results: list[VisionResult] = []
            for media_id in claim.media_ids:
                if self.vision is None:
                    raise FacebookResponseError("FACEBOOK_IMAGE_INPUT_DISABLED", retryable=False)
                source_url = await self.service.media_source(claim, media_id)
                try:
                    image = await self.media_downloader.download(source_url)
                except FacebookMediaError as exc:
                    if not exc.retryable:
                        await self.service.fail_media(claim, media_id, exc.safe_code)
                    raise
                object_key = (
                    f"workspaces/{claim.workspace_id}/facebook-media/"
                    f"{claim.inbound_message_id}/{secrets.token_urlsafe(18)}.{image.extension}"
                )
                await self.service.mark_media_uploading(claim, media_id, object_key)
                try:
                    await self.storage.upload(
                        object_key=object_key,
                        content=image.content,
                        content_type=image.content_type,
                    )
                except VisitorImageStorageError as exc:
                    await self.service.fail_media(claim, media_id, "STORAGE_UNAVAILABLE")
                    raise FacebookResponseError("STORAGE_UNAVAILABLE", retryable=False) from exc
                await self.service.complete_media(
                    claim,
                    media_id,
                    content_type=image.content_type,
                    content=image.content,
                    width=image.width,
                    height=image.height,
                )
                try:
                    vision_result = await self.vision.analyze(
                        content=image.content, content_type=image.content_type
                    )
                except VisionTemporaryError as exc:
                    raise FacebookResponseError("VISION_UNAVAILABLE", retryable=False) from exc
                except VisionPermanentError as exc:
                    raise FacebookResponseError("VISION_REJECTED", retryable=False) from exc
                question_parts.append(vision_result.observation.prompt_context())
                vision_results.append(vision_result)
            question = "\n\n".join(question_parts)
            if not question:
                raise FacebookResponseError("FACEBOOK_INPUT_UNSUPPORTED", retryable=False)
            revision = await self.service.session.get(AgentRevision, claim.revision_id)
            if revision is None or revision.workspace_id != claim.workspace_id:
                raise FacebookResponseError("RESPONSE_CONTEXT_MISSING", retryable=False)
            context = await resolve_revision_execution_context(self.service.session, revision)
            runtime = self.runtime_factory(self.service.session)
            response = await runtime.run_with_context(
                context, question=question, history=claim.history
            )
            rendered = self.renderer.render(
                NormalizedOutboundMessage(
                    text=response.text,
                    product_links=tuple(
                        card.product_url
                        for card in response.product_cards
                        if card.product_url is not None
                    ),
                    source_labels=tuple(source.document_title for source in response.sources),
                )
            )
            await self.service.session.rollback()
            await self.service.complete(
                claim,
                text=rendered.text,
                response_json=response.model_dump(mode="json"),
                usage=response.usage,
                vision_results=tuple(vision_results),
            )
        except FacebookMediaError as exc:
            await self.service.session.rollback()
            await self.service.fail(claim, safe_code=exc.safe_code, retryable=exc.retryable)
        except (FacebookResponseError, ChannelRenderError, AgentRuntimeError) as exc:
            await self.service.session.rollback()
            safe_code = getattr(exc, "safe_code", getattr(exc, "code", str(exc)))
            retryable = getattr(exc, "retryable", False)
            await self.service.fail(claim, safe_code=safe_code, retryable=retryable)
        return True
