import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.catalog.models import CatalogCollection, Location
from agent_hub_api.channels.models import ChannelAgentBinding, ChannelConnection
from agent_hub_api.conversations.models import Conversation
from agent_hub_api.core.config import Settings
from agent_hub_api.identity.models import User
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.knowledge.models import AgentKnowledgeBase, KnowledgeBase
from agent_hub_api.main import create_app
from agent_hub_api.models import Base
from agent_hub_api.widget.models import WebsiteChannelConfig, WidgetDomain
from agent_hub_api.workspaces.models import WorkspaceMember

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"


class AppFactory(Protocol):
    def __call__(self) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]: ...


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    resources: list[AsyncEngine] = []

    def build() -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'overview.db'}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        app = create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
            ),
            session_factory=sessions,
        )
        resources.append(engine)
        return app, sessions

    yield build

    async def dispose() -> None:
        for engine in resources:
            await engine.dispose()

    asyncio.run(dispose())


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"x-csrf-token": token, "origin": ORIGIN}


def register_workspace(client: TestClient, email: str, slug: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 201, response.text
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": slug, "display_name": slug},
        headers=csrf_headers(client),
    )
    assert workspace.status_code == 201, workspace.text
    return cast(dict[str, Any], workspace.json())


def test_overview_is_tenant_scoped_and_projects_real_agent_relationships(
    app_factory: AppFactory,
) -> None:
    app, sessions = app_factory()
    owner_a = TestClient(app)
    owner_b = TestClient(app)
    member = TestClient(app)
    workspace_a = register_workspace(owner_a, "overview-a@example.com", "overview-a")
    workspace_b = register_workspace(owner_b, "overview-b@example.com", "overview-b")
    register_workspace(member, "overview-member@example.com", "overview-member")

    created = owner_a.post(
        f"/api/v1/workspaces/{workspace_a['id']}/agents",
        json={
            "name": "Support Agent",
            "default_locale": "vi",
            "icon": "headphones",
            "color": "#2F5BEA",
        },
        headers=csrf_headers(owner_a),
    )
    assert created.status_code == 201, created.text
    public_agent_id = UUID(created.json()["public_id"])

    async def seed() -> None:
        async with sessions() as session, session.begin():
            agent = await session.scalar(
                select(Agent).where(
                    Agent.workspace_id == UUID(workspace_a["id"]),
                    Agent.public_id == public_agent_id,
                )
            )
            user = await session.scalar(
                select(User).where(User.normalized_email == "overview-a@example.com")
            )
            member_user = await session.scalar(
                select(User).where(User.normalized_email == "overview-member@example.com")
            )
            assert agent is not None and user is not None
            assert member_user is not None
            owner_membership = await session.scalar(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == UUID(workspace_a["id"]),
                    WorkspaceMember.user_id == user.id,
                )
            )
            assert owner_membership is not None
            session.add(
                WorkspaceMember(
                    workspace_id=UUID(workspace_a["id"]),
                    user_id=member_user.id,
                    role="member",
                )
            )
            knowledge = KnowledgeBase(
                workspace_id=UUID(workspace_a["id"]), name="Support policy", kind="policy"
            )
            session.add(knowledge)
            await session.flush()
            session.add(
                AgentKnowledgeBase(
                    workspace_id=UUID(workspace_a["id"]),
                    agent_id=agent.id,
                    knowledge_base_id=knowledge.id,
                )
            )
            revision = AgentRevision(
                workspace_id=UUID(workspace_a["id"]),
                agent_id=agent.id,
                revision_no=1,
                name=agent.name,
                greeting=agent.greeting,
                safe_instructions=agent.safe_instructions,
                default_locale=agent.default_locale,
                catalog_scope_json={"location_ids": [], "collection_ids": []},
                knowledge_base_ids_json=[knowledge.id],
                widget_config_json={},
                config_hash="a" * 64,
                created_by_user_id=user.id,
            )
            session.add(revision)
            await session.flush()
            connection = ChannelConnection(
                workspace_id=UUID(workspace_a["id"]),
                provider="web",
                display_name="Website",
                lifecycle_state="active",
                health_state="healthy",
            )
            session.add(connection)
            await session.flush()
            session.add_all(
                [
                    ChannelAgentBinding(
                        workspace_id=UUID(workspace_a["id"]),
                        connection_id=connection.id,
                        agent_id=agent.id,
                        active_revision_id=revision.id,
                        enabled=True,
                    ),
                    WebsiteChannelConfig(
                        workspace_id=UUID(workspace_a["id"]), connection_id=connection.id
                    ),
                    WidgetDomain(
                        workspace_id=UUID(workspace_a["id"]),
                        channel_id=connection.id,
                        normalized_origin="https://example.com",
                    ),
                    Conversation(
                        public_id=uuid4(),
                        workspace_id=UUID(workspace_a["id"]),
                        agent_id=agent.id,
                        revision_id=revision.id,
                        channel_connection_id=connection.id,
                        workflow_status="pending",
                        handling_mode="human",
                        last_message_at=datetime.now(UTC),
                        retention_until=datetime.now(UTC) + timedelta(days=30),
                    ),
                    Conversation(
                        public_id=uuid4(),
                        workspace_id=UUID(workspace_a["id"]),
                        agent_id=agent.id,
                        revision_id=revision.id,
                        channel_connection_id=connection.id,
                        assigned_member_id=owner_membership.id,
                        workflow_status="open",
                        handling_mode="ai",
                        last_message_at=datetime.now(UTC),
                        retention_until=datetime.now(UTC) + timedelta(days=30),
                    ),
                ]
            )

    asyncio.run(seed())

    response = owner_a.get(f"/api/v1/workspaces/{workspace_a['id']}/overview?days=7")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["workspace_id"] == workspace_a["id"]
    assert payload["capabilities"]["catalog"] == {"available": False, "can_setup": True}
    assert payload["agent_total"] == 1
    assert payload["agents"][0]["public_id"] == str(public_agent_id)
    assert payload["agents"][0]["icon"] == "headphones"
    assert payload["agents"][0]["color"] == "#2F5BEA"
    assert payload["agents"][0]["knowledge"]["items"][0]["name"] == "Support policy"
    assert payload["agents"][0]["channels"]["web"]["total"] == 1
    assert payload["agents"][0]["website_readiness"]["can_publish"] is True
    assert payload["agents"][0]["conversations"]["total"] == 2
    assert payload["agents"][0]["conversations"]["human_handling"] == 1
    assert "handover_pending" in payload["agents"][0]["attention_reasons"]
    assert "normalized_origin" not in response.text

    engine = cast(AsyncEngine, sessions.kw["bind"])
    statement_count = 0

    def count_statement(*_args: object) -> None:
        nonlocal statement_count
        statement_count += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count_statement)
    owner_a.get(f"/api/v1/workspaces/{workspace_a['id']}/overview")
    single_agent_queries = statement_count
    for index in range(4):
        added = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/agents",
            json={"name": f"Agent {index}", "default_locale": "vi"},
            headers=csrf_headers(owner_a),
        )
        assert added.status_code == 201, added.text
    statement_count = 0
    owner_a.get(f"/api/v1/workspaces/{workspace_a['id']}/overview")
    event.remove(engine.sync_engine, "before_cursor_execute", count_statement)
    assert statement_count == single_agent_queries

    member_response = member.get(f"/api/v1/workspaces/{workspace_a['id']}/overview")
    assert member_response.status_code == 200, member_response.text
    assert member_response.json()["role"] == "member"
    assert member_response.json()["agents"][0]["conversations"]["total"] == 1
    assert member_response.json()["capabilities"]["catalog"]["can_setup"] is False

    denied = owner_b.get(f"/api/v1/workspaces/{workspace_a['id']}/overview")
    assert denied.status_code == 404
    own = owner_b.get(f"/api/v1/workspaces/{workspace_b['id']}/overview")
    assert own.status_code == 200
    assert own.json()["agents"] == []
    invalid_days = owner_a.get(
        f"/api/v1/workspaces/{workspace_a['id']}/overview?days=14"
    )
    assert invalid_days.status_code == 422

    async def enable_commerce() -> None:
        async with sessions() as session, session.begin():
            session.add_all(
                [
                    Location(
                        workspace_id=UUID(workspace_a["id"]),
                        name="Main location",
                        type="store",
                    ),
                    CatalogCollection(
                        workspace_id=UUID(workspace_a["id"]), name="Featured"
                    ),
                ]
            )

    asyncio.run(enable_commerce())
    commerce = owner_a.get(f"/api/v1/workspaces/{workspace_a['id']}/overview")
    assert commerce.status_code == 200, commerce.text
    assert commerce.json()["capabilities"]["catalog"] == {
        "available": True,
        "can_setup": False,
    }
    assert commerce.json()["agents"][0]["catalog_scope"]["locations"]["items"][0][
        "name"
    ] == "Main location"
