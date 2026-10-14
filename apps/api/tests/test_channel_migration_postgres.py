import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from agent_hub_api.core.config import normalize_database_url

pytestmark = pytest.mark.postgres
TEST_SCHEMA = "agenthub_test"
API_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(API_ROOT.parents[1] / ".env", override=False)


def _database_url() -> str:
    if os.getenv("RUN_POSTGRES_INTEGRATION_TESTS", "").casefold() != "true":
        pytest.skip("Set RUN_POSTGRES_INTEGRATION_TESTS=true to run destructive schema tests")
    if os.getenv("APP_ENV", "local").casefold() not in {"local", "test"}:
        pytest.fail("PostgreSQL integration tests only run when APP_ENV is local or test")
    value = os.getenv("DATABASE_URL")
    if not value:
        pytest.skip("DATABASE_URL is not configured")
    return normalize_database_url(value)


def _migrate(revision: str, *, downgrade: bool = False) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes["target_schema"] = TEST_SCHEMA
    operation = command.downgrade if downgrade else command.upgrade
    operation(config, revision)


def _reset_schema(database_url: str, *, create: bool) -> None:
    async def reset() -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE')
                if create:
                    await connection.exec_driver_sql(f'CREATE SCHEMA "{TEST_SCHEMA}"')
        finally:
            await engine.dispose()

    asyncio.run(reset())


def test_shared_channel_migration_rehearses_website_backfill_and_downgrade() -> None:
    database_url = _database_url()
    _reset_schema(database_url, create=True)
    try:
        _migrate("20261005_0013")

        user_id = uuid4()
        workspace_id = uuid4()
        agent_public_id = uuid4()
        conversation_public_id = uuid4()
        now = datetime.now(UTC)

        async def seed_and_verify() -> None:
            engine = create_async_engine(
                database_url,
                connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
            )
            try:
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO users (id, normalized_email, password_hash)
                            VALUES (:user_id, :email, 'test')
                            """
                        ),
                        {"user_id": user_id, "email": f"migration-{user_id}@example.test"},
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO workspaces (id, slug, display_name)
                            VALUES (:workspace_id, :slug, 'Migration rehearsal')
                            """
                        ),
                        {"workspace_id": workspace_id, "slug": f"migration-{workspace_id}"},
                    )
                    agent_id = await connection.scalar(
                        text(
                            """
                            INSERT INTO agents
                                (public_id, workspace_id, name, status, created_by_user_id)
                            VALUES
                                (:public_id, :workspace_id, 'Website agent', 'published', :user_id)
                            RETURNING id
                            """
                        ),
                        {
                            "public_id": agent_public_id,
                            "workspace_id": workspace_id,
                            "user_id": user_id,
                        },
                    )
                    revision_id = await connection.scalar(
                        text(
                            """
                            INSERT INTO agent_revisions
                                (workspace_id, agent_id, revision_no, name, default_locale,
                                 catalog_scope_json, knowledge_base_ids_json, widget_config_json,
                                 config_hash, created_by_user_id)
                            VALUES
                                (:workspace_id, :agent_id, 1, 'Website agent', 'vi', '{}'::jsonb,
                                 '[]'::jsonb, '{}'::jsonb, :config_hash, :user_id)
                            RETURNING id
                            """
                        ),
                        {
                            "workspace_id": workspace_id,
                            "agent_id": agent_id,
                            "config_hash": "a" * 64,
                            "user_id": user_id,
                        },
                    )
                    channel_id = await connection.scalar(
                        text(
                            """
                            INSERT INTO agent_web_channels
                                (workspace_id, agent_id, brand_color, launcher_position,
                                 handoff_url, handoff_label, active_revision_id, enabled)
                            VALUES
                                (:workspace_id, :agent_id, '#123456', 'left',
                                 'https://example.test/help', 'Help', :revision_id, true)
                            RETURNING id
                            """
                        ),
                        {
                            "workspace_id": workspace_id,
                            "agent_id": agent_id,
                            "revision_id": revision_id,
                        },
                    )
                    session_id = await connection.scalar(
                        text(
                            """
                            INSERT INTO widget_sessions
                                (workspace_id, agent_id, channel_id, revision_id, token_hash,
                                 normalized_origin, expires_at)
                            VALUES
                                (:workspace_id, :agent_id, :channel_id, :revision_id, :token_hash,
                                 'https://example.test', :expires_at)
                            RETURNING id
                            """
                        ),
                        {
                            "workspace_id": workspace_id,
                            "agent_id": agent_id,
                            "channel_id": channel_id,
                            "revision_id": revision_id,
                            "token_hash": "b" * 64,
                            "expires_at": now + timedelta(hours=24),
                        },
                    )
                    conversation_id = await connection.scalar(
                        text(
                            """
                            INSERT INTO conversations
                                (public_id, workspace_id, agent_id, revision_id, session_id,
                                 status, last_message_at, retention_until)
                            VALUES
                                (:public_id, :workspace_id, :agent_id, :revision_id, :session_id,
                                 'open', :now, :retention_until)
                            RETURNING id
                            """
                        ),
                        {
                            "public_id": conversation_public_id,
                            "workspace_id": workspace_id,
                            "agent_id": agent_id,
                            "revision_id": revision_id,
                            "session_id": session_id,
                            "now": now,
                            "retention_until": now + timedelta(hours=24),
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO conversation_messages
                                (workspace_id, conversation_id, sequence_no, actor, text, status,
                                 completed_at)
                            VALUES
                                (:workspace_id, :conversation_id, 1, 'visitor', 'hello',
                                 'completed', :now),
                                (:workspace_id, :conversation_id, 2, 'assistant', 'hi',
                                 'completed', :now)
                            """
                        ),
                        {
                            "workspace_id": workspace_id,
                            "conversation_id": conversation_id,
                            "now": now,
                        },
                    )

                await asyncio.to_thread(_migrate, "20261006_0014")

                async with engine.connect() as connection:
                    migrated = (
                        await connection.execute(
                            text(
                                """
                                SELECT c.id, c.provider, c.display_name, c.lifecycle_state,
                                       c.health_state, b.agent_id, b.active_revision_id, b.enabled,
                                       w.brand_color, w.launcher_position, w.handoff_url,
                                       w.handoff_label
                                FROM channel_connections c
                                JOIN channel_agent_bindings b ON b.connection_id = c.id
                                JOIN website_channel_configs w ON w.connection_id = c.id
                                WHERE c.id = :channel_id
                                """
                            ),
                            {"channel_id": channel_id},
                        )
                    ).one()
                    assert migrated == (
                        channel_id,
                        "web",
                        "Website agent",
                        "active",
                        "healthy",
                        agent_id,
                        revision_id,
                        True,
                        "#123456",
                        "left",
                        "https://example.test/help",
                        "Help",
                    )
                    conversation = (
                        await connection.execute(
                            text(
                                """
                                SELECT public_id, channel_connection_id, session_id,
                                       lifecycle_state, workflow_status, handling_mode
                                FROM conversations WHERE id = :conversation_id
                                """
                            ),
                            {"conversation_id": conversation_id},
                        )
                    ).one()
                    assert conversation == (
                        conversation_public_id,
                        channel_id,
                        session_id,
                        "active",
                        "open",
                        "ai",
                    )
                    direction_rows = (
                        await connection.execute(
                            text(
                                """
                                SELECT actor, direction FROM conversation_messages
                                WHERE conversation_id = :conversation_id ORDER BY sequence_no
                                """
                            ),
                            {"conversation_id": conversation_id},
                        )
                    ).all()
                    directions = [(row.actor, row.direction) for row in direction_rows]
                    assert directions == [("visitor", "inbound"), ("assistant", "outbound")]

                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO channel_thread_mappings
                                (workspace_id, connection_id, conversation_id,
                                 external_thread_id, last_seen_at)
                            VALUES
                                (:workspace_id, :connection_id, :conversation_id,
                                 'migration-thread', :last_seen_at)
                            """
                        ),
                        {
                            "workspace_id": workspace_id,
                            "connection_id": channel_id,
                            "conversation_id": conversation_id,
                            "last_seen_at": now,
                        },
                    )
                    outbound_message_id = await connection.scalar(
                        text(
                            """
                            SELECT id FROM conversation_messages
                            WHERE conversation_id = :conversation_id AND sequence_no = 2
                            """
                        ),
                        {"conversation_id": conversation_id},
                    )
                    delivery_id = await connection.scalar(
                        text(
                            """
                            INSERT INTO outbound_deliveries
                                (workspace_id, connection_id, message_id, idempotency_key,
                                 state, provider_message_id)
                            VALUES
                                (:workspace_id, :connection_id, :message_id, 'legacy-delivery',
                                 'delivered', 'legacy-provider-mid')
                            RETURNING id
                            """
                        ),
                        {
                            "workspace_id": workspace_id,
                            "connection_id": channel_id,
                            "message_id": outbound_message_id,
                        },
                    )

                await asyncio.to_thread(_migrate, "20261008_0015")

                async with engine.begin() as connection:
                    delivery = (
                        await connection.execute(
                            text(
                                """
                                SELECT state, accepted_at, delivered_at
                                FROM outbound_deliveries WHERE id = :delivery_id
                                """
                            ),
                            {"delivery_id": delivery_id},
                        )
                    ).one()
                    assert delivery.state == "accepted"
                    assert delivery.accepted_at is not None
                    assert delivery.delivered_at is None
                    await connection.execute(
                        text(
                            """
                            INSERT INTO channel_delivery_receipts
                                (workspace_id, connection_id, provider_message_id,
                                 external_thread_id, delivered_at)
                            VALUES
                                (:workspace_id, :connection_id, 'legacy-provider-mid',
                                 'website-thread', :delivered_at)
                            """
                        ),
                        {
                            "workspace_id": workspace_id,
                            "connection_id": channel_id,
                            "delivered_at": now,
                        },
                    )

                await asyncio.to_thread(_migrate, "20261008_0016")

                async with engine.connect() as connection:
                    policy = (
                        await connection.execute(
                            text(
                                """
                                SELECT last_inbound_at, automation_state
                                FROM channel_thread_mappings
                                WHERE connection_id = :connection_id
                                """
                            ),
                            {"connection_id": channel_id},
                        )
                    ).one()
                    assert policy.last_inbound_at is not None
                    assert policy.automation_state == "opted_in"
                    assert (
                        await connection.scalar(text("SELECT to_regclass('channel_response_jobs')"))
                        == "channel_response_jobs"
                    )
                    assert (
                        await connection.scalar(text("SELECT to_regclass('channel_inbound_media')"))
                        == "channel_inbound_media"
                    )

                await asyncio.to_thread(_migrate, "20261014_0017")

                async with engine.connect() as connection:
                    assert (
                        await connection.scalar(
                            text("SELECT to_regclass('channel_oauth_attempts')")
                        )
                        == "channel_oauth_attempts"
                    )

                await asyncio.to_thread(_migrate, "20261008_0016", downgrade=True)

                async with engine.connect() as connection:
                    assert (
                        await connection.scalar(
                            text("SELECT to_regclass('channel_oauth_attempts')")
                        )
                        is None
                    )

                await asyncio.to_thread(_migrate, "20261008_0015", downgrade=True)

                async with engine.connect() as connection:
                    assert (
                        await connection.scalar(text("SELECT to_regclass('channel_response_jobs')"))
                        is None
                    )
                    assert (
                        await connection.scalar(text("SELECT to_regclass('channel_inbound_media')"))
                        is None
                    )

                await asyncio.to_thread(_migrate, "20261006_0014", downgrade=True)

                async with engine.connect() as connection:
                    restored_delivery_state = await connection.scalar(
                        text("SELECT state FROM outbound_deliveries WHERE id = :delivery_id"),
                        {"delivery_id": delivery_id},
                    )
                    assert restored_delivery_state == "delivered"
                    receipt_table = await connection.scalar(
                        text("SELECT to_regclass('channel_delivery_receipts')")
                    )
                    assert receipt_table is None

                await asyncio.to_thread(_migrate, "20261005_0013", downgrade=True)

                async with engine.connect() as connection:
                    restored = (
                        await connection.execute(
                            text(
                                """
                                SELECT wc.id, wc.agent_id, wc.active_revision_id, wc.enabled,
                                       c.public_id, c.status, m.actor
                                FROM agent_web_channels wc
                                JOIN widget_sessions s ON s.channel_id = wc.id
                                JOIN conversations c ON c.session_id = s.id
                                JOIN conversation_messages m ON m.conversation_id = c.id
                                WHERE wc.id = :channel_id AND m.sequence_no = 2
                                """
                            ),
                            {"channel_id": channel_id},
                        )
                    ).one()
                    assert restored == (
                        channel_id,
                        agent_id,
                        revision_id,
                        True,
                        conversation_public_id,
                        "open",
                        "assistant",
                    )
            finally:
                await engine.dispose()

        asyncio.run(seed_and_verify())
    finally:
        _reset_schema(database_url, create=False)
