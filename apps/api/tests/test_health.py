import asyncio
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import APPLICATION_DATABASE_REVISION
from agent_hub_api.main import app, create_app
from agent_hub_api.models import Base


async def prepare_health_database(engine: AsyncEngine, revision: str) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        await connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision},
        )


def test_health_returns_safe_liveness_payload() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "AgentHub API",
        "environment": "local",
    }
    assert "database" not in response.text.lower()


def test_explicit_liveness_matches_compatibility_endpoint() -> None:
    with TestClient(app) as client:
        assert client.get("/health/live").json() == client.get("/health").json()


def test_readiness_fails_safely_without_database() -> None:
    test_app = create_app(
        settings=Settings(
            app_env="test",
            database_url=None,
            jwt_signing_key="test-signing-key-with-at-least-32-bytes",
        )
    )

    with TestClient(test_app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "AgentHub API",
        "environment": "test",
        "database": "unavailable",
    }


def test_readiness_fails_safely_for_driver_timeout() -> None:
    class TimeoutSession:
        async def __aenter__(self) -> "TimeoutSession":
            raise TimeoutError

        async def __aexit__(self, *args: object) -> None:
            return None

    def timeout_session_factory() -> TimeoutSession:
        return TimeoutSession()

    test_app = create_app(
        settings=Settings(
            app_env="test",
            database_url=None,
            jwt_signing_key="test-signing-key-with-at-least-32-bytes",
        ),
        session_factory=cast(
            async_sessionmaker[AsyncSession],
            timeout_session_factory,
        ),
    )

    with TestClient(test_app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"


@pytest.fixture
def ready_client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'health.db'}")
    asyncio.run(prepare_health_database(engine, APPLICATION_DATABASE_REVISION))
    test_app = create_app(
        settings=Settings(
            app_env="test",
            database_url=None,
            jwt_signing_key="test-signing-key-with-at-least-32-bytes",
        ),
        session_factory=async_sessionmaker(engine, expire_on_commit=False),
    )
    with TestClient(test_app) as client:
        yield client
    asyncio.run(engine.dispose())


def test_readiness_checks_database_without_provider_calls(ready_client: TestClient) -> None:
    response = ready_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "AgentHub API",
        "environment": "test",
        "database": "ok",
    }


def test_readiness_fails_safely_for_stale_schema(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'stale-health.db'}")
    asyncio.run(prepare_health_database(engine, "20261005_0013"))
    test_app = create_app(
        settings=Settings(
            app_env="test",
            database_url=None,
            jwt_signing_key="test-signing-key-with-at-least-32-bytes",
        ),
        session_factory=async_sessionmaker(engine, expire_on_commit=False),
    )

    with TestClient(test_app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "AgentHub API",
        "environment": "test",
        "database": "unavailable",
    }
    assert "20261005_0013" not in response.text
    assert APPLICATION_DATABASE_REVISION not in response.text
    asyncio.run(engine.dispose())


def test_request_log_uses_route_template_and_omits_sensitive_input(
    ready_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="agent_hub_api.requests")

    response = ready_client.get(
        "/health?email=private@example.com&token=raw-secret",
        headers={"authorization": "Bearer raw-secret"},
    )

    assert response.status_code == 200
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "http_request request_id=" in messages
    assert "method=GET route=/health status_code=200" in messages
    assert "private@example.com" not in messages
    assert "raw-secret" not in messages
