import asyncio
import hashlib
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.channels.contracts import (
    ChannelCapabilities,
    NormalizedInboundMessage,
    NormalizedOutboundMessage,
    VerifiedInboundEvent,
)
from agent_hub_api.channels.models import (
    ChannelAgentBinding,
    ChannelConnection,
    ChannelDeliveryReceipt,
    ChannelThreadMapping,
    ChannelWebhookEvent,
    OutboundDelivery,
)
from agent_hub_api.channels.rendering import CapabilityAwareRenderer, ChannelRenderError
from agent_hub_api.channels.service import ChannelService, ChannelStateError
from agent_hub_api.contacts.models import Contact, ContactIdentity
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import Workspace


def test_capability_renderer_preserves_supported_evidence_and_falls_back_safely() -> None:
    message = NormalizedOutboundMessage(
        text="Bạn có thể xem sản phẩm này.",
        product_links=("https://shop.example/products/linen",),
        source_labels=("Chính sách đổi trả",),
    )
    rich = CapabilityAwareRenderer(
        provider="web",
        capabilities=ChannelCapabilities(product_cards=True, source_references=True),
        max_text_characters=1_000,
    ).render(message)
    assert rich.fallback_used is False
    assert rich.product_links == message.product_links
    assert rich.source_labels == message.source_labels

    text_only = CapabilityAwareRenderer(
        provider="facebook",
        capabilities=ChannelCapabilities(),
        max_text_characters=1_000,
    ).render(message)
    assert text_only.fallback_used is True
    assert message.product_links[0] in text_only.text
    assert "Chính sách đổi trả" in text_only.text
    assert text_only.product_links == ()
    assert text_only.source_labels == ()

    with pytest.raises(ChannelRenderError, match="INVALID_PRODUCT_LINK"):
        CapabilityAwareRenderer(
            provider="zalo",
            capabilities=ChannelCapabilities(),
            max_text_characters=1_000,
        ).render(NormalizedOutboundMessage(text="Xem", product_links=("javascript:alert(1)",)))


@pytest.fixture
def channel_database(
    tmp_path: Path,
) -> Iterator[tuple[async_sessionmaker[AsyncSession], AsyncEngine]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'channels.db'}")

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory, engine
    asyncio.run(engine.dispose())


async def seed_connection(
    factory: async_sessionmaker[AsyncSession],
    *,
    workspace_id: UUID,
    slug: str,
    external_account_id: str,
) -> ChannelConnection:
    user_id = uuid4()
    async with factory() as session, session.begin():
        workspace = Workspace(id=workspace_id, slug=slug, display_name=slug)
        agent = Agent(
            public_id=uuid4(),
            workspace_id=workspace_id,
            name="Channel agent",
            status="published",
            created_by_user_id=user_id,
        )
        session.add_all((workspace, agent))
        await session.flush()
        revision = AgentRevision(
            workspace_id=workspace_id,
            agent_id=agent.id,
            revision_no=1,
            name=agent.name,
            default_locale="vi",
            catalog_scope_json={},
            knowledge_base_ids_json=[],
            widget_config_json={},
            config_hash="a" * 64,
            created_by_user_id=user_id,
        )
        connection = ChannelConnection(
            workspace_id=workspace_id,
            provider="facebook",
            display_name=slug,
            external_account_id=external_account_id,
        )
        session.add_all((revision, connection))
        await session.flush()
        session.add(
            ChannelAgentBinding(
                workspace_id=workspace_id,
                connection_id=connection.id,
                agent_id=agent.id,
                active_revision_id=revision.id,
                enabled=True,
            )
        )
    return connection


def inbound_event(
    *,
    account: str,
    event_id: str,
    message_id: str,
    thread_id: str = "thread-shared",
    occurred_at: datetime | None = None,
) -> VerifiedInboundEvent:
    fingerprint = hashlib.sha256(f"{account}:{event_id}:{message_id}".encode()).hexdigest()
    return VerifiedInboundEvent(
        provider="facebook",
        external_account_id=account,
        external_event_id=event_id,
        payload_fingerprint=fingerprint,
        message=NormalizedInboundMessage(
            external_message_id=message_id,
            external_thread_id=thread_id,
            text="Xin chào",
            occurred_at=occurred_at,
        ),
    )


def test_verified_inbound_is_connection_scoped_deduplicated_and_mode_aware(
    channel_database: tuple[async_sessionmaker[AsyncSession], AsyncEngine],
) -> None:
    factory, _ = channel_database
    workspace_a = uuid4()
    workspace_b = uuid4()
    now = datetime.now(UTC)
    retention = now + timedelta(days=30)

    async def scenario() -> None:
        connection_a = await seed_connection(
            factory,
            workspace_id=workspace_a,
            slug="channel-a",
            external_account_id="account-a",
        )
        connection_b = await seed_connection(
            factory,
            workspace_id=workspace_b,
            slug="channel-b",
            external_account_id="account-b",
        )
        first_event = inbound_event(
            account="account-a",
            event_id="event-1",
            message_id="message-shared",
            occurred_at=now,
        )
        async with factory() as session:
            first = await ChannelService(session).ingest_verified(
                first_event, retention_until=retention
            )
        assert first.workspace_id == workspace_a
        assert first.connection_id == connection_a.id
        assert first.duplicate is False
        assert first.should_generate is True

        async with factory() as session:
            replay = await ChannelService(session).ingest_verified(
                first_event, retention_until=retention
            )
        assert replay.message_id == first.message_id
        assert replay.duplicate is True
        assert replay.should_generate is False

        same_message_new_event = inbound_event(
            account="account-a",
            event_id="event-2",
            message_id="message-shared",
            occurred_at=now - timedelta(minutes=5),
        )
        async with factory() as session:
            reordered = await ChannelService(session).ingest_verified(
                same_message_new_event, retention_until=retention
            )
        assert reordered.message_id == first.message_id
        assert reordered.duplicate is True

        async with factory() as session, session.begin():
            conversation = await session.get(Conversation, first.conversation_id)
            assert conversation is not None
            conversation.handling_mode = "human"

        next_event = inbound_event(account="account-a", event_id="event-3", message_id="message-2")
        async with factory() as session:
            human = await ChannelService(session).ingest_verified(
                next_event, retention_until=retention
            )
        assert human.conversation_id == first.conversation_id
        assert human.should_generate is False

        other_connection_event = inbound_event(
            account="account-b", event_id="event-1", message_id="message-shared"
        )
        async with factory() as session:
            other = await ChannelService(session).ingest_verified(
                other_connection_event, retention_until=retention
            )
        assert other.workspace_id == workspace_b
        assert other.connection_id == connection_b.id
        assert other.message_id != first.message_id

        conflict = replace(first_event, payload_fingerprint="f" * 64)
        async with factory() as session:
            with pytest.raises(ChannelStateError, match="EVENT_IDEMPOTENCY_CONFLICT"):
                await ChannelService(session).ingest_verified(conflict, retention_until=retention)

        async with factory() as session:
            assert await session.scalar(select(func.count(Conversation.id))) == 2
            assert await session.scalar(select(func.count(ConversationMessage.id))) == 3
            assert await session.scalar(select(func.count(ChannelWebhookEvent.id))) == 4
            assert await session.scalar(select(func.count(Contact.id))) == 2
            assert await session.scalar(select(func.count(ContactIdentity.id))) == 2
            first_conversation = await session.get(Conversation, first.conversation_id)
            other_conversation = await session.get(Conversation, other.conversation_id)
            assert first_conversation is not None
            assert first_conversation.contact_id is not None
            assert other_conversation is not None
            assert other_conversation.contact_id is not None
            assert other_conversation.contact_id != first_conversation.contact_id
            thread = (
                await session.scalars(
                    select(ChannelThreadMapping).where(
                        ChannelThreadMapping.connection_id == connection_a.id
                    )
                )
            ).one()
            assert thread.last_seen_at.replace(tzinfo=UTC) >= now

    asyncio.run(scenario())


def test_delivery_receipts_are_connection_scoped_and_reconcile_after_acceptance(
    channel_database: tuple[async_sessionmaker[AsyncSession], AsyncEngine],
) -> None:
    factory, _ = channel_database
    workspace_a = uuid4()
    workspace_b = uuid4()
    now = datetime.now(UTC)

    async def queue_for(connection: ChannelConnection, *, key: str) -> OutboundDelivery:
        async with factory() as session, session.begin():
            binding = (
                await session.scalars(
                    select(ChannelAgentBinding).where(
                        ChannelAgentBinding.connection_id == connection.id
                    )
                )
            ).one()
            assert binding.active_revision_id is not None
            conversation = Conversation(
                public_id=uuid4(),
                workspace_id=connection.workspace_id,
                agent_id=binding.agent_id,
                revision_id=binding.active_revision_id,
                channel_connection_id=connection.id,
                retention_until=now + timedelta(days=30),
            )
            session.add(conversation)
            await session.flush()
            thread = ChannelThreadMapping(
                workspace_id=connection.workspace_id,
                connection_id=connection.id,
                conversation_id=conversation.id,
                external_thread_id="shared-psid",
            )
            message = ConversationMessage(
                workspace_id=connection.workspace_id,
                conversation_id=conversation.id,
                sequence_no=1,
                actor="assistant",
                direction="outbound",
                text="Hello",
                status="completed",
                completed_at=now,
            )
            session.add_all((thread, message))
            await session.flush()
            thread_id = thread.id
            message_id = message.id
        async with factory() as session:
            return await ChannelService(session).queue_delivery(
                workspace_id=connection.workspace_id,
                connection_id=connection.id,
                thread_mapping_id=thread_id,
                message_id=message_id,
                idempotency_key=key,
            )

    async def scenario() -> None:
        connection_a = await seed_connection(
            factory,
            workspace_id=workspace_a,
            slug="receipt-a",
            external_account_id="page-a",
        )
        connection_b = await seed_connection(
            factory,
            workspace_id=workspace_b,
            slug="receipt-b",
            external_account_id="page-b",
        )
        delivery_a = await queue_for(connection_a, key="receipt-a")
        delivery_b = await queue_for(connection_b, key="receipt-b")

        async with factory() as session:
            claim_a = await ChannelService(session).claim_delivery(now=now + timedelta(minutes=1))
        assert claim_a is not None
        async with factory() as session:
            await ChannelService(session).complete_delivery(
                claim_a, external_message_id="same-provider-mid"
            )
        async with factory() as session:
            claim_b = await ChannelService(session).claim_delivery(now=now + timedelta(minutes=1))
        assert claim_b is not None
        async with factory() as session:
            await ChannelService(session).complete_delivery(
                claim_b, external_message_id="same-provider-mid"
            )

        delivered_at = now + timedelta(minutes=2)
        async with factory() as session:
            matched = await ChannelService(session).record_delivery_receipts(
                provider="facebook",
                external_account_id="page-a",
                external_thread_id="shared-psid",
                external_message_ids=("same-provider-mid",),
                delivered_at=delivered_at,
            )
        assert matched == 1

        async with factory() as session:
            stored_a = await session.get(OutboundDelivery, delivery_a.id)
            stored_b = await session.get(OutboundDelivery, delivery_b.id)
            assert stored_a is not None and stored_a.state == "delivered"
            assert stored_a.delivered_at == delivered_at.replace(tzinfo=None)
            assert stored_b is not None and stored_b.state == "accepted"
            receipts = (await session.scalars(select(ChannelDeliveryReceipt))).all()
            assert len(receipts) == 1
            assert receipts[0].workspace_id == workspace_a
            assert receipts[0].connection_id == connection_a.id

    asyncio.run(scenario())


def test_outbound_delivery_enforces_scope_lease_and_bounded_retry(
    channel_database: tuple[async_sessionmaker[AsyncSession], AsyncEngine],
) -> None:
    factory, _ = channel_database
    workspace_id = uuid4()
    other_workspace_id = uuid4()
    now = datetime.now(UTC)

    async def scenario() -> None:
        connection = await seed_connection(
            factory,
            workspace_id=workspace_id,
            slug="delivery-a",
            external_account_id="delivery-account",
        )
        async with factory() as session, session.begin():
            binding = (
                await session.scalars(
                    select(ChannelAgentBinding).where(
                        ChannelAgentBinding.connection_id == connection.id
                    )
                )
            ).one()
            assert binding.active_revision_id is not None
            conversation = Conversation(
                public_id=uuid4(),
                workspace_id=workspace_id,
                agent_id=binding.agent_id,
                revision_id=binding.active_revision_id,
                channel_connection_id=connection.id,
                retention_until=now + timedelta(days=30),
            )
            session.add(conversation)
            await session.flush()
            thread = ChannelThreadMapping(
                workspace_id=workspace_id,
                connection_id=connection.id,
                conversation_id=conversation.id,
                external_thread_id="thread-1",
            )
            message = ConversationMessage(
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                sequence_no=1,
                actor="assistant",
                direction="outbound",
                text="Phản hồi",
                status="completed",
                completed_at=now,
            )
            session.add_all((thread, message))
            await session.flush()
            thread_id = thread.id
            message_id = message.id

        async with factory() as session:
            service = ChannelService(session)
            with pytest.raises(ChannelStateError, match="DELIVERY_SCOPE_MISMATCH"):
                await service.queue_delivery(
                    workspace_id=other_workspace_id,
                    connection_id=connection.id,
                    thread_mapping_id=thread_id,
                    message_id=message_id,
                    idempotency_key="delivery-1",
                )

        async with factory() as session:
            delivery = await ChannelService(session).queue_delivery(
                workspace_id=workspace_id,
                connection_id=connection.id,
                thread_mapping_id=thread_id,
                message_id=message_id,
                idempotency_key="delivery-1",
                max_attempts=2,
            )
        async with factory() as session:
            replay = await ChannelService(session).queue_delivery(
                workspace_id=workspace_id,
                connection_id=connection.id,
                thread_mapping_id=thread_id,
                message_id=message_id,
                idempotency_key="delivery-1",
                max_attempts=2,
            )
        assert replay.id == delivery.id

        async with factory() as session:
            first_claim = await ChannelService(session).claim_delivery(
                now=now + timedelta(seconds=1)
            )
        assert first_claim is not None
        async with factory() as session:
            await ChannelService(session).fail_delivery(
                first_claim,
                safe_error_code="PROVIDER_BUSY",
                retryable=True,
                now=now + timedelta(seconds=1),
            )
        async with factory() as session:
            second_claim = await ChannelService(session).claim_delivery(
                now=now + timedelta(seconds=3)
            )
        assert second_claim is not None
        async with factory() as session:
            await ChannelService(session).fail_delivery(
                second_claim,
                safe_error_code="PROVIDER_BUSY",
                retryable=True,
                now=now + timedelta(seconds=3),
            )
        async with factory() as session:
            assert (
                await ChannelService(session).claim_delivery(now=now + timedelta(minutes=10))
                is None
            )
            stored = await session.get(OutboundDelivery, delivery.id)
            assert stored is not None
            assert stored.state == "failed_terminal"
            assert stored.attempt_count == 2
            assert stored.safe_error_code == "PROVIDER_BUSY"

        async with factory() as session, session.begin():
            accepted_message = ConversationMessage(
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                sequence_no=2,
                actor="human",
                direction="outbound",
                text="Đã tiếp nhận",
                status="completed",
                completed_at=now,
            )
            session.add(accepted_message)
            await session.flush()
            accepted_message_id = accepted_message.id
        async with factory() as session:
            accepted = await ChannelService(session).queue_delivery(
                workspace_id=workspace_id,
                connection_id=connection.id,
                thread_mapping_id=thread_id,
                message_id=accepted_message_id,
                idempotency_key="delivery-accepted",
            )
        async with factory() as session:
            accepted_claim = await ChannelService(session).claim_delivery(
                now=now + timedelta(minutes=20)
            )
        assert accepted_claim is not None
        async with factory() as session:
            with pytest.raises(ChannelStateError, match="DELIVERY_LEASE_LOST"):
                await ChannelService(session).complete_delivery(
                    replace(accepted_claim, lease_token="stale-lease"),
                    external_message_id="provider-message-1",
                )
        async with factory() as session:
            await ChannelService(session).complete_delivery(
                accepted_claim, external_message_id="provider-message-1"
            )
        async with factory() as session:
            assert (
                await ChannelService(session).claim_delivery(now=now + timedelta(hours=1)) is None
            )
            stored = await session.get(OutboundDelivery, accepted.id)
            assert stored is not None
            assert stored.state == "accepted"
            assert stored.provider_message_id == "provider-message-1"
            assert stored.accepted_at is not None
            assert stored.delivered_at is None

        async with factory() as session, session.begin():
            abandoned_message = ConversationMessage(
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                sequence_no=3,
                actor="assistant",
                direction="outbound",
                text="Thử một lần",
                status="completed",
                completed_at=now,
            )
            session.add(abandoned_message)
            await session.flush()
            abandoned_message_id = abandoned_message.id
        async with factory() as session:
            abandoned = await ChannelService(session).queue_delivery(
                workspace_id=workspace_id,
                connection_id=connection.id,
                thread_mapping_id=thread_id,
                message_id=abandoned_message_id,
                idempotency_key="delivery-abandoned",
                max_attempts=1,
            )
        async with factory() as session:
            abandoned_claim = await ChannelService(session).claim_delivery(
                now=now + timedelta(hours=2), lease_seconds=1
            )
        assert abandoned_claim is not None
        async with factory() as session:
            assert (
                await ChannelService(session).claim_delivery(
                    now=now + timedelta(hours=2, seconds=2)
                )
                is None
            )
            stored = await session.get(OutboundDelivery, abandoned.id)
            assert stored is not None
            assert stored.state == "failed_terminal"
            assert stored.safe_error_code == "DELIVERY_LEASE_EXPIRED"

        async with factory() as session, session.begin():
            revoked_message = ConversationMessage(
                workspace_id=workspace_id,
                conversation_id=conversation.id,
                sequence_no=4,
                actor="human",
                direction="outbound",
                text="Connection revoked",
                status="completed",
                completed_at=now,
            )
            session.add(revoked_message)
            await session.flush()
            revoked_message_id = revoked_message.id
        async with factory() as session:
            revoked_delivery = await ChannelService(session).queue_delivery(
                workspace_id=workspace_id,
                connection_id=connection.id,
                thread_mapping_id=thread_id,
                message_id=revoked_message_id,
                idempotency_key="delivery-revoked",
            )
        async with factory() as session, session.begin():
            stored_connection = await session.get(ChannelConnection, connection.id)
            assert stored_connection is not None
            stored_connection.lifecycle_state = "revoked"
        async with factory() as session:
            assert (
                await ChannelService(session).claim_delivery(now=now + timedelta(hours=3)) is None
            )
            stored = await session.get(OutboundDelivery, revoked_delivery.id)
            assert stored is not None
            assert stored.state == "failed_terminal"
            assert stored.safe_error_code == "CONNECTION_INACTIVE"

    asyncio.run(scenario())
