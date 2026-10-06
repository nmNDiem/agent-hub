from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.channels.models import (
    ChannelAgentBinding,
    ChannelConnection,
    ChannelMessageMapping,
    ChannelThreadMapping,
    ChannelWebhookEvent,
    OutboundDelivery,
)
from agent_hub_api.conversations.models import Conversation, ConversationMessage


class ChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def connection_for_external_account(
        self, provider: str, external_account_id: str, *, for_update: bool = False
    ) -> ChannelConnection | None:
        statement = select(ChannelConnection).where(
            ChannelConnection.provider == provider,
            ChannelConnection.external_account_id == external_account_id,
            ChannelConnection.lifecycle_state == "active",
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.scalars(statement)).one_or_none()

    async def connection_for_update(
        self, workspace_id: UUID, connection_id: int
    ) -> ChannelConnection | None:
        return (
            await self.session.scalars(
                select(ChannelConnection)
                .where(
                    ChannelConnection.workspace_id == workspace_id,
                    ChannelConnection.id == connection_id,
                    ChannelConnection.lifecycle_state == "active",
                )
                .with_for_update()
            )
        ).one_or_none()

    async def binding(self, connection: ChannelConnection) -> ChannelAgentBinding | None:
        return (
            await self.session.scalars(
                select(ChannelAgentBinding).where(
                    ChannelAgentBinding.workspace_id == connection.workspace_id,
                    ChannelAgentBinding.connection_id == connection.id,
                    ChannelAgentBinding.enabled.is_(True),
                    ChannelAgentBinding.active_revision_id.is_not(None),
                )
            )
        ).one_or_none()

    async def webhook_event(
        self, connection_id: int, external_event_id: str
    ) -> ChannelWebhookEvent | None:
        return (
            await self.session.scalars(
                select(ChannelWebhookEvent).where(
                    ChannelWebhookEvent.connection_id == connection_id,
                    ChannelWebhookEvent.external_event_id == external_event_id,
                )
            )
        ).one_or_none()

    async def thread(
        self, connection: ChannelConnection, external_thread_id: str, *, for_update: bool = False
    ) -> ChannelThreadMapping | None:
        statement = select(ChannelThreadMapping).where(
            ChannelThreadMapping.workspace_id == connection.workspace_id,
            ChannelThreadMapping.connection_id == connection.id,
            ChannelThreadMapping.external_thread_id == external_thread_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.scalars(statement)).one_or_none()

    async def mapped_message(
        self, connection: ChannelConnection, external_message_id: str
    ) -> ChannelMessageMapping | None:
        return (
            await self.session.scalars(
                select(ChannelMessageMapping).where(
                    ChannelMessageMapping.workspace_id == connection.workspace_id,
                    ChannelMessageMapping.connection_id == connection.id,
                    ChannelMessageMapping.external_message_id == external_message_id,
                )
            )
        ).one_or_none()

    async def conversation_for_update(
        self, workspace_id: UUID, conversation_id: int
    ) -> Conversation | None:
        return (
            await self.session.scalars(
                select(Conversation)
                .where(
                    Conversation.workspace_id == workspace_id,
                    Conversation.id == conversation_id,
                    Conversation.lifecycle_state == "active",
                )
                .with_for_update()
            )
        ).one_or_none()

    async def last_sequence(self, conversation_id: int) -> int:
        latest = await self.session.scalar(
            select(ConversationMessage.sequence_no)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.sequence_no.desc())
            .limit(1)
        )
        return int(latest or 0)

    async def delivery_by_key(
        self, connection_id: int, idempotency_key: str
    ) -> OutboundDelivery | None:
        return (
            await self.session.scalars(
                select(OutboundDelivery).where(
                    OutboundDelivery.connection_id == connection_id,
                    OutboundDelivery.idempotency_key == idempotency_key,
                )
            )
        ).one_or_none()

    async def claimable_delivery(self, now: datetime) -> OutboundDelivery | None:
        return (
            await self.session.scalars(
                select(OutboundDelivery)
                .where(
                    OutboundDelivery.attempt_count < OutboundDelivery.max_attempts,
                    or_(
                        and_(
                            OutboundDelivery.state.in_(("queued", "failed_retryable")),
                            OutboundDelivery.next_attempt_at <= now,
                        ),
                        and_(
                            OutboundDelivery.state == "sending",
                            OutboundDelivery.lease_expires_at <= now,
                        ),
                    ),
                )
                .order_by(OutboundDelivery.next_attempt_at, OutboundDelivery.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).one_or_none()

    async def terminalize_exhausted_leases(self, now: datetime) -> None:
        await self.session.execute(
            update(OutboundDelivery)
            .where(
                OutboundDelivery.state == "sending",
                OutboundDelivery.attempt_count >= OutboundDelivery.max_attempts,
                OutboundDelivery.lease_expires_at <= now,
            )
            .values(
                state="failed_terminal",
                safe_error_code="DELIVERY_LEASE_EXPIRED",
                lease_token=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )

    async def delivery_context(
        self, delivery: OutboundDelivery
    ) -> tuple[ChannelConnection, ConversationMessage, ChannelThreadMapping] | None:
        row = (
            await self.session.execute(
                select(ChannelConnection, ConversationMessage, ChannelThreadMapping)
                .select_from(ChannelConnection)
                .join(
                    ConversationMessage,
                    (ConversationMessage.workspace_id == delivery.workspace_id)
                    & (ConversationMessage.id == delivery.message_id),
                )
                .join(
                    ChannelMessageMapping,
                    (ChannelMessageMapping.workspace_id == delivery.workspace_id)
                    & (ChannelMessageMapping.connection_id == delivery.connection_id)
                    & (ChannelMessageMapping.message_id == delivery.message_id),
                )
                .join(
                    ChannelThreadMapping,
                    (ChannelThreadMapping.workspace_id == ChannelMessageMapping.workspace_id)
                    & (ChannelThreadMapping.id == ChannelMessageMapping.thread_mapping_id),
                )
                .where(
                    ChannelConnection.workspace_id == delivery.workspace_id,
                    ChannelConnection.id == delivery.connection_id,
                )
            )
        ).one_or_none()
        return (
            cast(tuple[ChannelConnection, ConversationMessage, ChannelThreadMapping], row)
            if row
            else None
        )
