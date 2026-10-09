from unittest.mock import patch

from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import create_database_engine


def test_database_engine_uses_bounded_pool_and_connect_timeout() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql://user:password@example.test/database",
        database_pool_size=3,
        database_pool_max_overflow=1,
        database_pool_timeout_seconds=7,
        database_connect_timeout_seconds=9,
    )

    with patch("agent_hub_api.core.database.create_async_engine") as factory:
        engine = factory.return_value

        result = create_database_engine(settings)

    assert result is engine
    factory.assert_called_once_with(
        "postgresql+asyncpg://user:password@example.test/database",
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=1,
        pool_timeout=7,
        connect_args={"timeout": 9},
    )


def test_database_engine_requires_url() -> None:
    settings = Settings(app_env="test", database_url=None)

    try:
        create_database_engine(settings)
    except ValueError as exc:
        assert str(exc) == "DATABASE_URL is required to create the database engine"
    else:
        raise AssertionError("Missing database URL must be rejected")
