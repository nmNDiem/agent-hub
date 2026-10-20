import asyncio
import os
from pathlib import Path

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


def test_follow_up_migration_upgrades_and_downgrades(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = _database_url()
    monkeypatch.setenv("APP_ENV", "test")
    _reset_schema(database_url, create=True)
    try:
        _migrate("20261020_0024")
        _migrate("20261020_0025")

        async def verify_upgrade() -> None:
            engine = create_async_engine(
                database_url,
                connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
            )
            try:
                async with engine.connect() as connection:
                    revision = await connection.scalar(
                        text("SELECT version_num FROM alembic_version")
                    )
                    execution_table = await connection.scalar(
                        text(
                            """
                            SELECT to_regclass('follow_up_action_executions') IS NOT NULL
                            """
                        )
                    )
                    agent_default = await connection.scalar(
                        text(
                            """
                            SELECT column_default
                            FROM information_schema.columns
                            WHERE table_schema = current_schema()
                              AND table_name = 'agents'
                              AND column_name = 'follow_up_action_enabled'
                            """
                        )
                    )
                    nullable_session = await connection.scalar(
                        text(
                            """
                            SELECT is_nullable
                            FROM information_schema.columns
                            WHERE table_schema = current_schema()
                              AND table_name = 'leads'
                              AND column_name = 'session_id'
                            """
                        )
                    )
                    assert revision == "20261020_0025"
                    assert execution_table is True
                    assert agent_default == "false"
                    assert nullable_session == "YES"
            finally:
                await engine.dispose()

        asyncio.run(verify_upgrade())
        _migrate("20261020_0024", downgrade=True)

        async def verify_downgrade() -> None:
            engine = create_async_engine(
                database_url,
                connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
            )
            try:
                async with engine.connect() as connection:
                    revision = await connection.scalar(
                        text("SELECT version_num FROM alembic_version")
                    )
                    execution_table = await connection.scalar(
                        text("SELECT to_regclass('follow_up_action_executions')")
                    )
                    action_column = await connection.scalar(
                        text(
                            """
                            SELECT count(*)
                            FROM information_schema.columns
                            WHERE table_schema = current_schema()
                              AND table_name = 'agents'
                              AND column_name = 'follow_up_action_enabled'
                            """
                        )
                    )
                    assert revision == "20261020_0024"
                    assert execution_table is None
                    assert action_column == 0
            finally:
                await engine.dispose()

        asyncio.run(verify_downgrade())
    finally:
        _reset_schema(database_url, create=False)
