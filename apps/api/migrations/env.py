import asyncio
import os
from logging.config import fileConfig
from pathlib import Path
from typing import Any

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from agent_hub_api.core.config import normalize_database_url
from agent_hub_api.models import Base

config = context.config
repository_root = Path(__file__).resolve().parents[3]
load_dotenv(repository_root / ".env", override=False)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url(*, allow_dialect_only: bool) -> str:
    database_url = os.getenv("AGENT_HUB_DATABASE_URL")
    if database_url:
        return normalize_database_url(database_url)
    if allow_dialect_only:
        return "postgresql+asyncpg://"
    raise RuntimeError(
        "AGENT_HUB_DATABASE_URL is required for online migrations. "
        "Copy the root .env.example to .env and provide a development database URL."
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(allow_dialect_only=True),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_database_url(allow_dialect_only=False)
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
