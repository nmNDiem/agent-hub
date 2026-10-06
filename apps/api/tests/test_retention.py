import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.leads.models import Lead
from agent_hub_api.models import Base
from agent_hub_api.operations.retention import RetentionSweeper, RetentionSweepResult
from agent_hub_api.telemetry.models import UsageEvent
from agent_hub_api.widget.image_storage import VisitorImageStorageError
from agent_hub_api.widget.models import (
    VisitorImageUpload,
    WidgetCatalogImageGrant,
    WidgetRateWindow,
    WidgetSession,
)
from agent_hub_api.workspaces.models import Workspace


class FakeStorage:
    def __init__(self) -> None:
        self.fail = True
        self.deleted: list[str] = []

    async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None:
        del object_key, content, content_type

    async def download(self, *, object_key: str, max_bytes: int) -> bytes:
        del object_key, max_bytes
        return b""

    async def delete(self, *, object_key: str) -> None:
        if self.fail:
            raise VisitorImageStorageError("test failure")
        self.deleted.append(object_key)


@pytest.fixture
def retention_database(
    tmp_path: Path,
) -> Iterator[tuple[async_sessionmaker[AsyncSession], AsyncEngine]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retention.db'}")

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory, engine
    asyncio.run(engine.dispose())


def test_sweeper_revokes_retries_and_preserves_live_workspace_data(
    retention_database: tuple[async_sessionmaker[AsyncSession], AsyncEngine],
) -> None:
    factory, _ = retention_database
    storage = FakeStorage()
    now = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
    expired = now - timedelta(minutes=1)
    live_until = now + timedelta(hours=1)
    expired_workspace_id = uuid4()
    live_workspace_id = uuid4()

    async def seed() -> tuple[int, int, int, int, int, int, int]:
        async with factory() as session, session.begin():
            session.add_all(
                [
                    Workspace(
                        id=expired_workspace_id,
                        slug="expired-shop",
                        display_name="Expired shop",
                    ),
                    Workspace(
                        id=live_workspace_id,
                        slug="live-shop",
                        display_name="Live shop",
                    ),
                ]
            )
            expired_session = WidgetSession(
                workspace_id=expired_workspace_id,
                agent_id=1,
                channel_id=1,
                revision_id=1,
                token_hash="a" * 64,
                normalized_origin="https://expired.example",
                expires_at=expired,
            )
            live_session = WidgetSession(
                workspace_id=live_workspace_id,
                agent_id=2,
                channel_id=2,
                revision_id=2,
                token_hash="b" * 64,
                normalized_origin="https://live.example",
                expires_at=live_until,
            )
            session.add_all([expired_session, live_session])
            await session.flush()
            expired_conversation = Conversation(
                public_id=uuid4(),
                workspace_id=expired_workspace_id,
                agent_id=1,
                revision_id=1,
                channel_connection_id=1,
                session_id=expired_session.id,
                lifecycle_state="active",
                retention_until=expired,
                last_message_at=expired,
            )
            live_conversation = Conversation(
                public_id=uuid4(),
                workspace_id=live_workspace_id,
                agent_id=2,
                revision_id=2,
                channel_connection_id=2,
                session_id=live_session.id,
                lifecycle_state="active",
                retention_until=live_until,
                last_message_at=now,
            )
            session.add_all([expired_conversation, live_conversation])
            await session.flush()
            expired_message = ConversationMessage(
                workspace_id=expired_workspace_id,
                conversation_id=expired_conversation.id,
                sequence_no=1,
                actor="visitor",
                direction="inbound",
                text="private expired chat",
                status="completed",
            )
            live_message = ConversationMessage(
                workspace_id=live_workspace_id,
                conversation_id=live_conversation.id,
                sequence_no=1,
                actor="visitor",
                direction="inbound",
                text="live chat",
                status="completed",
            )
            lead = Lead(
                workspace_id=expired_workspace_id,
                conversation_id=expired_conversation.id,
                session_id=expired_session.id,
                agent_id=1,
                name="Private visitor",
                normalized_email="private@example.com",
                phone=None,
                consent_at=expired - timedelta(days=30),
                consent_text_version="test-v1",
                idempotency_key="retention-test",
                request_hash="c" * 64,
                followup_status="new",
                retention_until=expired,
            )
            image = VisitorImageUpload(
                public_id=uuid4(),
                workspace_id=expired_workspace_id,
                session_id=expired_session.id,
                attached_conversation_id=expired_conversation.id,
                attached_request_key="turn-1",
                object_key="workspaces/expired/private.webp",
                content_type="image/webp",
                byte_size=100,
                width=10,
                height=10,
                sha256="d" * 64,
                status="attached",
                analysis_json={"private": "description"},
                expires_at=expired,
            )
            live_image = VisitorImageUpload(
                public_id=uuid4(),
                workspace_id=live_workspace_id,
                session_id=live_session.id,
                attached_conversation_id=live_conversation.id,
                attached_request_key="turn-live",
                object_key="workspaces/live/image.webp",
                content_type="image/webp",
                byte_size=100,
                width=10,
                height=10,
                sha256="e" * 64,
                status="attached",
                analysis_json={"safe": "still live"},
                expires_at=live_until,
            )
            grant = WidgetCatalogImageGrant(
                public_id=uuid4(),
                workspace_id=expired_workspace_id,
                session_id=expired_session.id,
                product_image_id=10,
                expires_at=expired,
            )
            rate_window = WidgetRateWindow(
                workspace_id=expired_workspace_id,
                scope="bootstrap_ip",
                key_hash="f" * 64,
                window_started_at=now - timedelta(hours=3),
                count=1,
            )
            usage = UsageEvent(
                workspace_id=expired_workspace_id,
                agent_id=1,
                conversation_id=expired_conversation.id,
                surface="widget",
                kind="generation",
                status="completed",
                model_calls=1,
                tool_calls=0,
                occurred_at=expired,
            )
            session.add_all(
                [
                    expired_message,
                    live_message,
                    lead,
                    image,
                    live_image,
                    grant,
                    rate_window,
                    usage,
                ]
            )
            await session.flush()
            return (
                expired_session.id,
                live_session.id,
                expired_conversation.id,
                live_conversation.id,
                image.id,
                live_image.id,
                usage.id,
            )

    ids = asyncio.run(seed())
    settings = Settings(
        app_env="test",
        jwt_signing_key="test-signing-key-with-at-least-32-bytes",
    )
    sweeper = RetentionSweeper(factory, settings, storage)

    first = asyncio.run(sweeper.run_once(now=now))
    assert first.sessions_revoked == 1
    assert first.conversations_revoked == 1
    assert first.leads_deleted == 1
    assert first.grants_deleted == 1
    assert first.rate_windows_deleted == 1
    assert first.images_deleted == 0
    assert first.image_cleanup_failed == 1
    assert first.conversations_deleted == 0
    assert first.sessions_deleted == 0

    async def assert_retryable_state() -> None:
        async with factory() as session:
            expired_session = await session.get(WidgetSession, ids[0])
            live_session = await session.get(WidgetSession, ids[1])
            expired_conversation = await session.get(Conversation, ids[2])
            live_conversation = await session.get(Conversation, ids[3])
            image = await session.get(VisitorImageUpload, ids[4])
            live_image = await session.get(VisitorImageUpload, ids[5])
            assert expired_session is not None
            assert expired_session.revoked_at is not None
            assert expired_session.revoked_at.replace(tzinfo=UTC) == now
            assert live_session is not None and live_session.revoked_at is None
            assert expired_conversation is not None
            assert expired_conversation.lifecycle_state == "deleted"
            assert live_conversation is not None and live_conversation.lifecycle_state == "active"
            assert image is not None
            assert image.status == "cleanup_pending"
            assert image.analysis_json is None
            assert image.cleanup_attempts == 1
            assert image.last_cleanup_error == "storage_delete_failed"
            assert live_image is not None and live_image.status == "attached"
            assert live_image.analysis_json == {"safe": "still live"}
            assert not list(
                await session.scalars(
                    select(ConversationMessage).where(
                        ConversationMessage.conversation_id == ids[2]
                    )
                )
            )
            assert await session.scalar(select(Lead.id)) is None

    asyncio.run(assert_retryable_state())

    storage.fail = False
    second = asyncio.run(sweeper.run_once(now=now))
    assert second.images_deleted == 1
    assert second.image_cleanup_failed == 0
    assert second.conversations_deleted == 1
    assert second.sessions_deleted == 1
    assert storage.deleted == ["workspaces/expired/private.webp"]

    async def assert_final_state() -> None:
        async with factory() as session:
            assert await session.get(VisitorImageUpload, ids[4]) is None
            assert await session.get(Conversation, ids[2]) is None
            assert await session.get(WidgetSession, ids[0]) is None
            assert await session.get(VisitorImageUpload, ids[5]) is not None
            assert await session.get(Conversation, ids[3]) is not None
            assert await session.get(WidgetSession, ids[1]) is not None
            usage = await session.get(UsageEvent, ids[6])
            assert usage is not None and usage.conversation_id is None

    asyncio.run(assert_final_state())
    third = asyncio.run(sweeper.run_once(now=now))
    assert third == RetentionSweepResult()


def test_sweeper_respects_batch_size(
    retention_database: tuple[async_sessionmaker[AsyncSession], AsyncEngine],
) -> None:
    factory, _ = retention_database
    now = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
    workspace_id = uuid4()

    async def seed() -> None:
        async with factory() as session, session.begin():
            session.add(
                Workspace(id=workspace_id, slug="batch-shop", display_name="Batch shop")
            )
            session.add_all(
                [
                    WidgetRateWindow(
                        workspace_id=workspace_id,
                        scope="bootstrap_ip",
                        key_hash=character * 64,
                        window_started_at=now - timedelta(hours=3),
                        count=1,
                    )
                    for character in ("a", "b")
                ]
            )

    asyncio.run(seed())
    settings = Settings(
        app_env="test",
        jwt_signing_key="test-signing-key-with-at-least-32-bytes",
    )
    sweeper = RetentionSweeper(factory, settings, None)

    assert asyncio.run(sweeper.run_once(now=now, batch_size=1)).rate_windows_deleted == 1
    assert asyncio.run(sweeper.run_once(now=now, batch_size=1)).rate_windows_deleted == 1
