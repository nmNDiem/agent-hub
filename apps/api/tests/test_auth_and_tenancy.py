import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.core.config import Settings
from agent_hub_api.identity.security import CSRF_COOKIE, REFRESH_COOKIE
from agent_hub_api.main import create_app
from agent_hub_api.models import Base, User, Workspace, WorkspaceMember

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"


class AppFactory(Protocol):
    def __call__(
        self, email_enabled: bool = False
    ) -> tuple[FastAPI, async_sessionmaker[AsyncSession], "CapturingEmailDelivery"]: ...


class CapturingEmailDelivery:
    def __init__(self) -> None:
        self.verification_tokens: list[str] = []
        self.reset_tokens: list[str] = []

    async def send_verification(self, *, recipient: str, token: str) -> None:
        self.verification_tokens.append(token)

    async def send_password_reset(self, *, recipient: str, token: str) -> None:
        self.reset_tokens.append(token)


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    resources: list[AsyncEngine] = []

    def build(
        email_enabled: bool = False,
    ) -> tuple[FastAPI, async_sessionmaker[AsyncSession], CapturingEmailDelivery]:
        database_path = tmp_path / f"test-{len(resources)}.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        delivery = CapturingEmailDelivery()
        settings = Settings(
            app_env="test",
            jwt_signing_key="test-signing-key-with-at-least-32-bytes",
            email_delivery_enabled=email_enabled,
        )
        app = create_app(
            settings=settings,
            session_factory=session_factory,
            email_delivery=delivery,
        )
        resources.append(engine)
        return app, session_factory, delivery

    yield build

    async def dispose() -> None:
        for engine in resources:
            await engine.dispose()

    asyncio.run(dispose())


def register(client: TestClient, email: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 201, response.text
    return response.json()


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"x-csrf-token": token, "origin": ORIGIN}


def test_registration_hashes_password_and_creates_no_implicit_workspace(
    app_factory: AppFactory,
) -> None:
    app, session_factory, _ = app_factory()
    with TestClient(app) as client:
        payload = register(client, "OWNER@Example.com")
        response = client.get("/api/v1/me")

    assert payload["user"]["email"] == "owner@example.com"
    assert response.status_code == 200
    assert response.json()["workspaces"] == []

    async def load_user() -> User:
        async with session_factory() as session:
            user = await session.scalar(select(User))
            assert user is not None
            return user

    user = asyncio.run(load_user())
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2id$")


def test_refresh_rotation_replay_revokes_the_token_family(app_factory: AppFactory) -> None:
    app, _, _ = app_factory()
    with TestClient(app) as client:
        register(client, "owner@example.com")
        old_refresh = client.cookies.get(REFRESH_COOKIE)
        old_csrf = client.cookies.get(CSRF_COOKIE)
        assert old_refresh and old_csrf

        rotated = client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
        assert rotated.status_code == 200
        new_refresh = client.cookies.get(REFRESH_COOKIE)
        new_csrf = client.cookies.get(CSRF_COOKIE)
        assert new_refresh and new_refresh != old_refresh and new_csrf

        replay = client.post(
            "/api/v1/auth/refresh",
            headers={
                "cookie": f"{REFRESH_COOKIE}={old_refresh}; {CSRF_COOKIE}={old_csrf}",
                "x-csrf-token": old_csrf,
                "origin": ORIGIN,
            },
        )
        assert replay.status_code == 401
        assert replay.json()["error"]["code"] == "SESSION_REPLAY"

        rejected_family = client.post(
            "/api/v1/auth/refresh",
            headers={
                "cookie": f"{REFRESH_COOKIE}={new_refresh}; {CSRF_COOKIE}={new_csrf}",
                "x-csrf-token": new_csrf,
                "origin": ORIGIN,
            },
        )
        assert rejected_family.status_code == 401


def test_logout_revokes_refresh_session(app_factory: AppFactory) -> None:
    app, _, _ = app_factory()
    with TestClient(app) as client:
        register(client, "owner@example.com")
        old_refresh = client.cookies.get(REFRESH_COOKIE)
        old_csrf = client.cookies.get(CSRF_COOKIE)
        assert old_refresh and old_csrf
        response = client.post("/api/v1/auth/logout", headers=csrf_headers(client))
        assert response.status_code == 204
        stale = client.post(
            "/api/v1/auth/refresh",
            headers={
                "cookie": f"{REFRESH_COOKIE}={old_refresh}; {CSRF_COOKIE}={old_csrf}",
                "x-csrf-token": old_csrf,
                "origin": ORIGIN,
            },
        )
        assert stale.status_code == 401


def test_workspace_reads_and_writes_are_tenant_scoped(app_factory: AppFactory) -> None:
    app, session_factory, _ = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        register(owner_a, "a@example.com")
        created_a = owner_a.post(
            "/api/v1/workspaces",
            json={"display_name": "Shop A", "slug": "shop-a"},
            headers=csrf_headers(owner_a),
        )
        assert created_a.status_code == 201

        register(owner_b, "b@example.com")
        created_b = owner_b.post(
            "/api/v1/workspaces",
            json={"display_name": "Shop B", "slug": "shop-b"},
            headers=csrf_headers(owner_b),
        )
        assert created_b.status_code == 201
        workspace_b_id = created_b.json()["id"]

        listed_a = owner_a.get("/api/v1/workspaces")
        assert [workspace["slug"] for workspace in listed_a.json()] == ["shop-a"]
        assert owner_a.get(f"/api/v1/workspaces/{workspace_b_id}").status_code == 404
        denied_update = owner_a.patch(
            f"/api/v1/workspaces/{workspace_b_id}",
            json={"display_name": "Stolen", "timezone": "UTC"},
            headers=csrf_headers(owner_a),
        )
        assert denied_update.status_code == 404
        assert (
            owner_b.get(f"/api/v1/workspaces/{workspace_b_id}").json()["display_name"] == "Shop B"
        )

        async def add_member_access() -> None:
            async with session_factory() as session:
                user_b = await session.scalar(
                    select(User).where(User.normalized_email == "b@example.com")
                )
                workspace_a = await session.scalar(
                    select(Workspace).where(Workspace.slug == "shop-a")
                )
                assert user_b is not None and workspace_a is not None
                session.add(
                    WorkspaceMember(workspace_id=workspace_a.id, user_id=user_b.id, role="member")
                )
                await session.commit()

        asyncio.run(add_member_access())
        workspace_a_id = created_a.json()["id"]
        assert owner_b.get(f"/api/v1/workspaces/{workspace_a_id}").status_code == 200
        forbidden_update = owner_b.patch(
            f"/api/v1/workspaces/{workspace_a_id}",
            json={"display_name": "Forbidden", "timezone": "UTC"},
            headers=csrf_headers(owner_b),
        )
        assert forbidden_update.status_code == 403


def test_duplicate_workspace_slug_rolls_back_the_whole_operation(
    app_factory: AppFactory,
) -> None:
    app, session_factory, _ = app_factory()
    with TestClient(app) as client:
        register(client, "owner@example.com")
        first = client.post(
            "/api/v1/workspaces",
            json={"display_name": "Shop A", "slug": "shared-slug"},
            headers=csrf_headers(client),
        )
        duplicate = client.post(
            "/api/v1/workspaces",
            json={"display_name": "Shop B", "slug": "shared-slug"},
            headers=csrf_headers(client),
        )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "WORKSPACE_SLUG_UNAVAILABLE"

    async def count_tenant_records() -> tuple[int, int]:
        async with session_factory() as session:
            workspace_count = await session.scalar(select(func.count()).select_from(Workspace))
            member_count = await session.scalar(select(func.count()).select_from(WorkspaceMember))
            assert workspace_count is not None and member_count is not None
            return workspace_count, member_count

    assert asyncio.run(count_tenant_records()) == (1, 1)


def test_reset_token_is_single_use_and_revokes_sessions(app_factory: AppFactory) -> None:
    app, _, delivery = app_factory(True)
    with TestClient(app) as client:
        register(client, "owner@example.com")
        assert len(delivery.verification_tokens) == 1
        verified = client.post(
            "/api/v1/auth/verify-email",
            json={"token": delivery.verification_tokens[-1]},
            headers={"origin": ORIGIN},
        )
        assert verified.status_code == 200
        assert client.get("/api/v1/me").json()["user"]["email_verified"] is True
        forgot = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "owner@example.com"},
            headers={"origin": ORIGIN},
        )
        assert forgot.status_code == 200
        token = delivery.reset_tokens[-1]
        reset = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "new-secure-password-456"},
            headers={"origin": ORIGIN},
        )
        assert reset.status_code == 200
        assert client.get("/api/v1/me").status_code == 401
        reused = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "another-password-789"},
            headers={"origin": ORIGIN},
        )
        assert reused.status_code == 400
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "new-secure-password-456"},
        )
        assert login.status_code == 200


def test_csrf_is_required_for_authenticated_mutations(app_factory: AppFactory) -> None:
    app, _, _ = app_factory()
    with TestClient(app) as client:
        register(client, "owner@example.com")
        response = client.post(
            "/api/v1/workspaces",
            json={"display_name": "Shop", "slug": "shop"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_FAILED"
        denied_origin = client.post(
            "/api/v1/workspaces",
            json={"display_name": "Shop", "slug": "shop"},
            headers={**csrf_headers(client), "origin": "https://attacker.example"},
        )
        assert denied_origin.status_code == 403
        assert denied_origin.json()["error"]["code"] == "ORIGIN_DENIED"
        assert client.post(
            "/api/v1/auth/forgot-password", json={"email": "owner@example.com"}
        ).status_code == 404
