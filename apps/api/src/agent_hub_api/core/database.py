from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import BigInteger, Integer
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from agent_hub_api.core.config import Settings

APPLICATION_DATABASE_REVISION = "20261008_0016"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


BIGINT_PRIMARY_KEY = BigInteger().with_variant(Integer, "sqlite")


def create_database_engine(settings: Settings) -> AsyncEngine:
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is required to create the database engine")
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_pool_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        connect_args={"timeout": settings.database_connect_timeout_seconds},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    async with session_factory() as session:
        yield session
