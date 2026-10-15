import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agents.db'}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app = create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
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


def register_and_create_workspace(
    client: TestClient, email: str, slug: str
) -> tuple[dict[str, Any], dict[str, Any]]:
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
    return cast(dict[str, Any], registration.json()), cast(dict[str, Any], workspace.json())


def test_agent_creation_supplies_editable_defaults_when_optional_copy_is_omitted(
    app_factory: AppFactory,
) -> None:
    app, _ = app_factory()
    with TestClient(app) as owner:
        _, workspace = register_and_create_workspace(owner, "defaults@example.com", "defaults")

        created = owner.post(
            f"/api/v1/workspaces/{workspace['id']}/agents",
            json={"name": "Tư vấn viên"},
            headers=csrf_headers(owner),
        )

        assert created.status_code == 201, created.text
        payload = created.json()
        assert payload["default_locale"] == "vi"
        assert payload["greeting"].startswith("Xin chào!")
        assert "tư vấn viên bán hàng" in payload["safe_instructions"]


def test_agent_api_persists_scope_and_enforces_workspace_and_role(
    app_factory: AppFactory,
) -> None:
    app, session_factory = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        _, workspace_a = register_and_create_workspace(owner_a, "a@example.com", "shop-a")
        user_b, workspace_b = register_and_create_workspace(owner_b, "b@example.com", "shop-b")

        location_a_response = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/locations",
            json={"name": "Hanoi", "code": "HN"},
            headers=csrf_headers(owner_a),
        )
        collection_a_response = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/catalog/collections",
            json={"name": "Featured"},
            headers=csrf_headers(owner_a),
        )
        location_b_response = owner_b.post(
            f"/api/v1/workspaces/{workspace_b['id']}/locations",
            json={"name": "Other", "code": "OTHER"},
            headers=csrf_headers(owner_b),
        )
        assert location_a_response.status_code == 201
        assert collection_a_response.status_code == 201
        assert location_b_response.status_code == 201
        location_a = location_a_response.json()
        collection_a = collection_a_response.json()
        location_b = location_b_response.json()

        created = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/agents",
            json={
                "name": "Shop assistant",
                "greeting": "Xin chào",
                "safe_instructions": "Only use verified catalog facts.",
            },
            headers=csrf_headers(owner_a),
        )
        assert created.status_code == 201, created.text
        agent = created.json()
        assert UUID(agent["public_id"]).version == 7
        assert agent["status"] == "draft"
        assert agent["catalog_scope"] == {"location_ids": None, "collection_ids": None}

        scoped = owner_a.put(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
            "/catalog-scope",
            json={
                "location_ids": [location_a["id"], location_a["id"]],
                "collection_ids": [collection_a["id"]],
            },
            headers=csrf_headers(owner_a),
        )
        assert scoped.status_code == 200, scoped.text
        assert scoped.json()["catalog_scope"] == {
            "location_ids": [location_a["id"]],
            "collection_ids": [collection_a["id"]],
        }

        denied_cross_workspace = owner_b.get(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
        )
        assert denied_cross_workspace.status_code == 404

        forged_assignment = owner_a.put(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
            "/catalog-scope",
            json={"location_ids": [location_b["id"]], "collection_ids": []},
            headers=csrf_headers(owner_a),
        )
        assert forged_assignment.status_code == 404
        unchanged = owner_a.get(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
        )
        assert unchanged.json()["catalog_scope"] == scoped.json()["catalog_scope"]

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
        assert (
            owner_b.get(
                f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
            ).status_code
            == 200
        )
        forbidden_member_write = owner_b.patch(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}",
            json={"name": "Forbidden"},
            headers=csrf_headers(owner_b),
        )
        assert forbidden_member_write.status_code == 403

        invalid_status_write = owner_a.patch(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}",
            json={"status": "published"},
            headers=csrf_headers(owner_a),
        )
        assert invalid_status_write.status_code == 422

        empty_scope = owner_a.put(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
            "/catalog-scope",
            json={"location_ids": [], "collection_ids": []},
            headers=csrf_headers(owner_a),
        )
        assert empty_scope.status_code == 200
        assert empty_scope.json()["catalog_scope"] == {
            "location_ids": [],
            "collection_ids": [],
        }

        listed = owner_a.get(f"/api/v1/workspaces/{workspace_a['id']}/agents")
        assert listed.status_code == 200
        assert [item["public_id"] for item in listed.json()["items"]] == [agent["public_id"]]


def test_agent_archive_enforces_workspace_role_and_hides_active_resource(
    app_factory: AppFactory,
) -> None:
    app, session_factory = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        _, workspace_a = register_and_create_workspace(
            owner_a, "archive-a@example.com", "archive-a"
        )
        user_b, workspace_b = register_and_create_workspace(
            owner_b, "archive-b@example.com", "archive-b"
        )
        created = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/agents",
            json={"name": "Archive me"},
            headers=csrf_headers(owner_a),
        )
        assert created.status_code == 201, created.text
        agent = created.json()

        missing_csrf = owner_a.delete(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
        )
        assert missing_csrf.status_code == 403

        cross_workspace = owner_b.delete(
            f"/api/v1/workspaces/{workspace_b['id']}/agents/{agent['public_id']}",
            headers=csrf_headers(owner_b),
        )
        assert cross_workspace.status_code == 404

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
        forbidden_member = owner_b.delete(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}",
            headers=csrf_headers(owner_b),
        )
        assert forbidden_member.status_code == 403

        archived = owner_a.delete(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}",
            headers=csrf_headers(owner_a),
        )
        assert archived.status_code == 204
        assert owner_a.get(
            f"/api/v1/workspaces/{workspace_a['id']}/agents/{agent['public_id']}"
        ).status_code == 404
        listed = owner_a.get(f"/api/v1/workspaces/{workspace_a['id']}/agents")
        assert listed.status_code == 200
        assert listed.json()["items"] == []
