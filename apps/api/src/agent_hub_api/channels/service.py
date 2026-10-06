import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.channels.contracts import (
    ChannelProvider,
    DeliveryRequest,
    OutboundAdapter,
    ProviderDeliveryError,
    RenderedOutboundMessage,
    VerifiedInboundEvent,
)
from agent_hub_api.channels.models import (
    ChannelMessageMapping,
    ChannelThreadMapping,
    ChannelWebhookEvent,
    OutboundDelivery,
)
from agent_hub_api.channels.repository import ChannelRepository
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.identifiers import new_uuid_v7


class ChannelStateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class InboundResult:
    workspace_id: UUID
    connection_id: int
    conversation_id: int
    message_id: int
    duplicate: bool
    should_generate: bool


@dataclass(frozen=True, slots=True)
class ClaimedDelivery:
    delivery_id: int
    workspace_id: UUID
    lease_token: str
    request: DeliveryRequest


class ChannelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ChannelRepository(session)

    async def ingest_verified(
        self, event: VerifiedInboundEvent, *, retention_until: datetime
    ) -> InboundResult:
        if retention_until.tzinfo is None:
            raise ValueError("Channel retention deadline must be timezone-aware")
        if event.message.attachments:
            raise ChannelStateError("UNSUPPORTED_ATTACHMENT")
        async with self.session.begin():
            connection = await self.repository.connection_for_external_account(
                event.provider, event.external_account_id, for_update=True
            )
            if connection is None:
                raise ChannelStateError("CONNECTION_NOT_FOUND")
            binding = await self.repository.binding(connection)
            if binding is None or binding.active_revision_id is None:
                raise ChannelStateError("CONNECTION_NOT_READY")
            existing_event = await self.repository.webhook_event(
                connection.id, event.external_event_id
            )
            if existing_event is not None:
                if existing_event.payload_fingerprint != event.payload_fingerprint:
                    raise ChannelStateError("EVENT_IDEMPOTENCY_CONFLICT")
                if existing_event.message_id is None:
                    raise ChannelStateError("EVENT_IN_PROGRESS")
                message = await self.session.get(ConversationMessage, existing_event.message_id)
                if message is None:
                    raise ChannelStateError("EVENT_MESSAGE_MISSING")
                conversation = await self.session.get(Conversation, message.conversation_id)
                if conversation is None or conversation.workspace_id != connection.workspace_id:
                    raise ChannelStateError("EVENT_CONVERSATION_MISSING")
                return InboundResult(
                    workspace_id=connection.workspace_id,
                    connection_id=connection.id,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    duplicate=True,
                    should_generate=False,
                )

            webhook = ChannelWebhookEvent(
                workspace_id=connection.workspace_id,
                connection_id=connection.id,
                external_event_id=event.external_event_id,
                payload_fingerprint=event.payload_fingerprint,
                provider_occurred_at=event.message.occurred_at,
            )
            self.session.add(webhook)
            await self.session.flush()

            mapped = await self.repository.mapped_message(
                connection, event.message.external_message_id
            )
            if mapped is not None:
                message = await self.session.get(ConversationMessage, mapped.message_id)
                if message is None:
                    raise ChannelStateError("MAPPED_MESSAGE_MISSING")
                conversation = await self.session.get(Conversation, message.conversation_id)
                if conversation is None:
                    raise ChannelStateError("MAPPED_CONVERSATION_MISSING")
                webhook.message_id = message.id
                webhook.state = "processed"
                webhook.processed_at = datetime.now(UTC)
                return InboundResult(
                    workspace_id=connection.workspace_id,
                    connection_id=connection.id,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    duplicate=True,
                    should_generate=False,
                )

            thread = await self.repository.thread(
                connection, event.message.external_thread_id, for_update=True
            )
            now = datetime.now(UTC)
            if thread is None:
                conversation = Conversation(
                    public_id=new_uuid_v7(),
                    workspace_id=connection.workspace_id,
                    agent_id=binding.agent_id,
                    revision_id=binding.active_revision_id,
                    channel_connection_id=connection.id,
                    retention_until=retention_until,
                )
                self.session.add(conversation)
                await self.session.flush()
                thread = ChannelThreadMapping(
                    workspace_id=connection.workspace_id,
                    connection_id=connection.id,
                    conversation_id=conversation.id,
                    external_thread_id=event.message.external_thread_id,
                    last_seen_at=event.message.occurred_at or now,
                )
                self.session.add(thread)
                await self.session.flush()
            else:
                conversation = await self.repository.conversation_for_update(
                    connection.workspace_id, thread.conversation_id
                )
                if conversation is None:
                    raise ChannelStateError("THREAD_CONVERSATION_UNAVAILABLE")
                observed_at = event.message.occurred_at or now
                if _aware(observed_at) > _aware(thread.last_seen_at):
                    thread.last_seen_at = observed_at

            message = ConversationMessage(
                workspace_id=connection.workspace_id,
                conversation_id=conversation.id,
                sequence_no=await self.repository.last_sequence(conversation.id) + 1,
                actor="visitor",
                direction="inbound",
                text=event.message.text,
                status="completed",
                completed_at=now,
            )
            self.session.add(message)
            await self.session.flush()
            self.session.add(
                ChannelMessageMapping(
                    workspace_id=connection.workspace_id,
                    connection_id=connection.id,
                    thread_mapping_id=thread.id,
                    message_id=message.id,
                    external_message_id=event.message.external_message_id,
                    direction="inbound",
                )
            )
            conversation.last_message_at = now
            webhook.message_id = message.id
            webhook.state = "processed"
            webhook.processed_at = now
            return InboundResult(
                workspace_id=connection.workspace_id,
                connection_id=connection.id,
                conversation_id=conversation.id,
                message_id=message.id,
                duplicate=False,
                should_generate=conversation.handling_mode == "ai",
            )

    async def queue_delivery(
        self,
        *,
        workspace_id: UUID,
        connection_id: int,
        thread_mapping_id: int,
        message_id: int,
        idempotency_key: str,
        max_attempts: int = 5,
    ) -> OutboundDelivery:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Delivery idempotency key must contain 1 to 128 characters")
        if max_attempts < 1 or max_attempts > 10:
            raise ValueError("Delivery max attempts must be between 1 and 10")
        async with self.session.begin():
            connection = await self.repository.connection_for_update(
                workspace_id, connection_id
            )
            if connection is None:
                raise ChannelStateError("DELIVERY_SCOPE_MISMATCH")
            existing = await self.repository.delivery_by_key(connection_id, idempotency_key)
            if existing is not None:
                if existing.workspace_id != workspace_id or existing.message_id != message_id:
                    raise ChannelStateError("DELIVERY_IDEMPOTENCY_CONFLICT")
                return existing
            thread = await self.session.get(ChannelThreadMapping, thread_mapping_id)
            message = await self.session.get(ConversationMessage, message_id)
            if (
                thread is None
                or message is None
                or thread.workspace_id != workspace_id
                or thread.connection_id != connection_id
                or message.workspace_id != workspace_id
                or message.conversation_id != thread.conversation_id
                or message.direction != "outbound"
            ):
                raise ChannelStateError("DELIVERY_SCOPE_MISMATCH")
            mapping = ChannelMessageMapping(
                workspace_id=workspace_id,
                connection_id=connection_id,
                thread_mapping_id=thread_mapping_id,
                message_id=message_id,
                direction="outbound",
            )
            delivery = OutboundDelivery(
                workspace_id=workspace_id,
                connection_id=connection_id,
                message_id=message_id,
                idempotency_key=idempotency_key,
                max_attempts=max_attempts,
                next_attempt_at=datetime.now(UTC),
            )
            self.session.add_all((mapping, delivery))
            await self.session.flush()
            return delivery

    async def claim_delivery(
        self, *, now: datetime | None = None, lease_seconds: int = 60
    ) -> ClaimedDelivery | None:
        if lease_seconds < 1 or lease_seconds > 300:
            raise ValueError("Delivery lease must be between 1 and 300 seconds")
        claim_time = now or datetime.now(UTC)
        async with self.session.begin():
            await self.repository.terminalize_exhausted_leases(claim_time)
            delivery = await self.repository.claimable_delivery(claim_time)
            if delivery is None:
                return None
            context = await self.repository.delivery_context(delivery)
            if context is None:
                delivery.state = "failed_terminal"
                delivery.safe_error_code = "DELIVERY_CONTEXT_MISSING"
                delivery.updated_at = claim_time
                return None
            connection, message, thread = context
            token = secrets.token_hex(32)
            delivery.state = "sending"
            delivery.attempt_count += 1
            delivery.lease_token = token
            delivery.lease_expires_at = claim_time + timedelta(seconds=lease_seconds)
            delivery.safe_error_code = None
            delivery.updated_at = claim_time
            return ClaimedDelivery(
                delivery_id=delivery.id,
                workspace_id=delivery.workspace_id,
                lease_token=token,
                request=DeliveryRequest(
                    delivery_id=delivery.id,
                    provider=cast(ChannelProvider, connection.provider),
                    credential_ref=connection.credential_ref,
                    external_thread_id=thread.external_thread_id,
                    idempotency_key=delivery.idempotency_key,
                    message=RenderedOutboundMessage(text=message.text),
                ),
            )

    async def complete_delivery(
        self, claim: ClaimedDelivery, *, external_message_id: str
    ) -> None:
        if not external_message_id or len(external_message_id) > 500:
            raise ValueError("Provider message ID must contain 1 to 500 characters")
        async with self.session.begin():
            delivery = await self._locked_claim(claim)
            delivery.state = "delivered"
            delivery.provider_message_id = external_message_id
            delivery.lease_token = None
            delivery.lease_expires_at = None
            delivery.safe_error_code = None
            delivery.updated_at = datetime.now(UTC)
            mapping = (
                await self.session.scalars(
                    select(ChannelMessageMapping).where(
                        ChannelMessageMapping.workspace_id == delivery.workspace_id,
                        ChannelMessageMapping.connection_id == delivery.connection_id,
                        ChannelMessageMapping.message_id == delivery.message_id,
                    )
                )
            ).one()
            mapping.external_message_id = external_message_id

    async def fail_delivery(
        self,
        claim: ClaimedDelivery,
        *,
        safe_error_code: str,
        retryable: bool,
        now: datetime | None = None,
    ) -> None:
        if not safe_error_code or len(safe_error_code) > 80:
            raise ValueError("Safe delivery error code must contain 1 to 80 characters")
        failed_at = now or datetime.now(UTC)
        async with self.session.begin():
            delivery = await self._locked_claim(claim)
            can_retry = retryable and delivery.attempt_count < delivery.max_attempts
            delivery.state = "failed_retryable" if can_retry else "failed_terminal"
            delivery.next_attempt_at = failed_at + timedelta(
                seconds=min(300, 2 ** max(0, delivery.attempt_count - 1))
            )
            delivery.safe_error_code = safe_error_code
            delivery.lease_token = None
            delivery.lease_expires_at = None
            delivery.updated_at = failed_at

    async def _locked_claim(self, claim: ClaimedDelivery) -> OutboundDelivery:
        delivery = await self.session.get(OutboundDelivery, claim.delivery_id, with_for_update=True)
        if (
            delivery is None
            or delivery.workspace_id != claim.workspace_id
            or delivery.state != "sending"
            or delivery.lease_token != claim.lease_token
        ):
            raise ChannelStateError("DELIVERY_LEASE_LOST")
        return delivery


class DeliveryRunner:
    def __init__(
        self, service: ChannelService, adapters: dict[ChannelProvider, OutboundAdapter]
    ) -> None:
        self.service = service
        self.adapters = adapters

    async def run_once(self) -> bool:
        claim = await self.service.claim_delivery()
        if claim is None:
            return False
        adapter = self.adapters.get(claim.request.provider)
        if adapter is None:
            await self.service.fail_delivery(
                claim, safe_error_code="ADAPTER_UNAVAILABLE", retryable=False
            )
            return True
        try:
            result = await adapter.deliver(claim.request)
        except ProviderDeliveryError as exc:
            await self.service.fail_delivery(
                claim, safe_error_code=exc.safe_code, retryable=exc.retryable
            )
        else:
            await self.service.complete_delivery(
                claim, external_message_id=result.external_message_id
            )
        return True
