import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.agents.models import AgentRevision
from agent_hub_api.core.config import Settings
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.main import create_app
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import WorkspaceMember

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"


class AppFactory(Protocol):
    def __call__(self) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]: ...


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    resources: list[AsyncEngine] = []

    def build() -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'widget-publish.db'}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app = create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                widget_public_base_url="http://127.0.0.1:4173",
            ),
            session_factory=session_factory,
        )
        resources.append(engine)
        return app, session_factory

    yield build

    async def dispose() -> None:
        for engine in resources:
            await engine.dispose()

    asyncio.run(dispose())


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"x-csrf-token": token, "origin": ORIGIN}


def create_workspace_and_agent(
    client: TestClient, email: str, slug: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert registration.status_code == 201, registration.text
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": slug, "display_name": slug},
        headers=csrf_headers(client),
    )
    assert workspace.status_code == 201, workspace.text
    agent = client.post(
        f"/api/v1/workspaces/{workspace.json()['id']}/agents",
        json={"name": "Trợ lý cửa hàng"},
        headers=csrf_headers(client),
    )
    assert agent.status_code == 201, agent.text
    return (
        cast(dict[str, Any], registration.json()),
        cast(dict[str, Any], workspace.json()),
        cast(dict[str, Any], agent.json()),
    )


def test_widget_publish_creates_immutable_snapshots_and_is_idempotent(
    app_factory: AppFactory,
) -> None:
    app, session_factory = app_factory()
    with TestClient(app) as client:
        _, workspace, agent = create_workspace_and_agent(client, "owner@example.com", "shop")
        base = f"/api/v1/workspaces/{workspace['id']}/agents/{agent['public_id']}"

        initial = client.get(f"{base}/widget")
        assert initial.status_code == 200
        assert initial.json()["readiness"]["can_publish"] is False

        configured = client.put(
            f"{base}/widget",
            json={
                "display_name": "Tư vấn sản phẩm",
                "greeting": "Xin chào từ website",
                "brand_color": "#0f8f87",
                "launcher_position": "left",
                "allowed_origins": ["https://SHOP.example.com/", "https://shop.example.com"],
            },
            headers=csrf_headers(client),
        )
        assert configured.status_code == 200, configured.text
        assert configured.json()["allowed_origins"] == ["https://shop.example.com"]
        assert configured.json()["brand_color"] == "#0F8F87"

        published = client.post(f"{base}/publish", headers=csrf_headers(client))
        assert published.status_code == 200, published.text
        assert published.json()["status"] == "published"
        assert published.json()["active_revision"]["revision_no"] == 1
        assert "data-agent-id" in published.json()["embed_snippet"]

        replay = client.post(f"{base}/publish", headers=csrf_headers(client))
        assert replay.status_code == 200
        assert replay.json()["active_revision"]["revision_no"] == 1

        changed = client.put(
            f"{base}/widget",
            json={
                "display_name": "Tên bản nháp",
                "greeting": "Lời chào mới",
                "brand_color": "#123456",
                "launcher_position": "right",
                "allowed_origins": ["https://shop.example.com"],
            },
            headers=csrf_headers(client),
        )
        assert changed.status_code == 200
        assert changed.json()["draft_differs"] is True
        assert changed.json()["active_revision"]["revision_no"] == 1

        republished = client.post(f"{base}/publish", headers=csrf_headers(client))
        assert republished.status_code == 200
        assert republished.json()["active_revision"]["revision_no"] == 2

        paused = client.post(f"{base}/pause", headers=csrf_headers(client))
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"
        assert paused.json()["enabled"] is False

    async def verify_revisions() -> None:
        async with session_factory() as session:
            revisions = list(
                await session.scalars(select(AgentRevision).order_by(AgentRevision.revision_no))
            )
            assert [revision.name for revision in revisions] == [
                "Tư vấn sản phẩm",
                "Tên bản nháp",
            ]
            assert revisions[0].widget_config_json["brand_color"] == "#0F8F87"

    asyncio.run(verify_revisions())


def test_widget_admin_enforces_origin_workspace_and_role(app_factory: AppFactory) -> None:
    app, session_factory = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        _, workspace_a, agent_a = create_workspace_and_agent(
            owner_a, "owner-a@example.com", "shop-a"
        )
        user_b, workspace_b, _ = create_workspace_and_agent(
            owner_b, "owner-b@example.com", "shop-b"
        )
        base = f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent_a['public_id']}"

        invalid_origin = owner_a.put(
            f"{base}/widget",
            json={
                "display_name": "Widget",
                "brand_color": "#0F8F87",
                "launcher_position": "right",
                "allowed_origins": ["http://shop.example.com"],
            },
            headers=csrf_headers(owner_a),
        )
        assert invalid_origin.status_code == 422

        assert owner_b.get(f"{base}/widget").status_code == 404

        async def add_member() -> None:
            async with session_factory() as session, session.begin():
                session.add(
                    WorkspaceMember(
                        workspace_id=UUID(workspace_a["id"]),
                        user_id=UUID(user_b["user"]["id"]),
                        role="member",
                    )
                )

        asyncio.run(add_member())
        assert owner_b.get(f"{base}/widget").status_code == 200
        denied = owner_b.put(
            f"{base}/widget",
            json={
                "display_name": "Forbidden",
                "brand_color": "#0F8F87",
                "launcher_position": "right",
                "allowed_origins": ["https://shop.example.com"],
            },
            headers=csrf_headers(owner_b),
        )
        assert denied.status_code == 403

        wrong_workspace = owner_a.get(
            f"/api/v1/workspaces/{workspace_b['id']}/agents/{agent_a['public_id']}/widget"
        )
        assert wrong_workspace.status_code == 404
