import asyncio
import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

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

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.channels.models import (
    ChannelConnection,
    ChannelOAuthAttempt,
    ChannelResponseJob,
    ChannelWebhookEvent,
)
from agent_hub_api.channels.responses import ChannelResponseService
from agent_hub_api.conversations.models import ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.main import create_app
from agent_hub_api.models import Base
from agent_hub_api.zalo.contracts import ZaloOAIdentity, ZaloTokenSet
from agent_hub_api.zalo.credentials import decode_bundle, encode_bundle
from agent_hub_api.zalo.tokens import ZaloTokenManager
from agent_hub_api.zalo.webhook import ZaloWebhookAdapter

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"
APP_ID = "123456789"
APP_SECRET = "zalo-test-app-secret"
WEBHOOK_SECRET = "zalo-oa-webhook-secret"


class FakeVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.revoked: list[str] = []

    async def store(self, *, workspace_id: UUID, plaintext: str) -> str:
        reference = f"fake:{workspace_id}:{len(self.values) + len(self.revoked) + 1}"
        self.values[reference] = plaintext
        return reference

    async def resolve(self, credential_ref: str) -> str:
        return self.values[credential_ref]

    async def revoke(self, credential_ref: str) -> None:
        self.values.pop(credential_ref, None)
        self.revoked.append(credential_ref)


class FakeZaloGateway:
    def __init__(self) -> None:
        self.exchange_verifiers: list[str] = []
        self.refreshes = 0
        self.sent: list[tuple[str, str]] = []

    async def exchange_code(self, *, code: str, code_verifier: str) -> ZaloTokenSet:
        assert code == "authorization-code"
        self.exchange_verifiers.append(code_verifier)
        return ZaloTokenSet("access-token", "refresh-token", 90_000)

    async def refresh_token(self, refresh_token: str) -> ZaloTokenSet:
        assert refresh_token == "refresh-token"
        self.refreshes += 1
        return ZaloTokenSet("refreshed-access", "refreshed-refresh", 90_000)

    async def get_oa(self, access_token: str) -> ZaloOAIdentity:
        assert access_token in {"access-token", "refreshed-access"}
        return ZaloOAIdentity(oa_id="oa-123", name="Example Zalo OA")

    async def send_text(self, *, recipient_id: str, text: str, access_token: str) -> str:
        assert access_token in {"access-token", "refreshed-access"}
        self.sent.append((recipient_id, text))
        return "zalo-message-1"


class AppFactory(Protocol):
    def __call__(
        self,
    ) -> tuple[
        FastAPI,
        async_sessionmaker[AsyncSession],
        FakeVault,
        FakeZaloGateway,
    ]: ...


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    resources: list[AsyncEngine] = []

    def build() -> tuple[
        FastAPI,
        async_sessionmaker[AsyncSession],
        FakeVault,
        FakeZaloGateway,
    ]:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'zalo.db'}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        vault = FakeVault()
        gateway = FakeZaloGateway()
        app = create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                zalo_app_id=APP_ID,
                zalo_app_secret=APP_SECRET,
                zalo_oauth_redirect_uri=(
                    "http://127.0.0.1:8000/api/v1/channels/zalo/oauth/callback"
                ),
                zalo_webhook_max_bytes=4096,
            ),
            session_factory=sessions,
            credential_vault=vault,
            zalo_gateway=gateway,
        )
        resources.append(engine)
        return app, sessions, vault, gateway

    yield build

    async def dispose() -> None:
        for engine in resources:
            await engine.dispose()

    asyncio.run(dispose())


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"x-csrf-token": token, "origin": ORIGIN}


def register_workspace(client: TestClient, *, email: str, slug: str) -> dict[str, Any]:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert registered.status_code == 201, registered.text
    created = client.post(
        "/api/v1/workspaces",
        json={"slug": slug, "display_name": slug},
        headers=csrf_headers(client),
    )
    assert created.status_code == 201, created.text
    return cast(dict[str, Any], created.json())


def create_published_agent(
    client: TestClient,
    sessions: async_sessionmaker[AsyncSession],
    workspace_id: str,
) -> str:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/agents",
        json={"name": "Zalo agent"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 201, response.text
    public_id = cast(str, response.json()["public_id"])

    async def publish() -> None:
        async with sessions() as session, session.begin():
            agent = (
                await session.scalars(select(Agent).where(Agent.public_id == UUID(public_id)))
            ).one()
            agent.status = "published"
            session.add(
                AgentRevision(
                    workspace_id=agent.workspace_id,
                    agent_id=agent.id,
                    revision_no=1,
                    name=agent.name,
                    default_locale="vi",
                    catalog_scope_json={"location_ids": None, "collection_ids": None},
                    knowledge_base_ids_json=[],
                    widget_config_json={},
                    config_hash="a" * 64,
                    created_by_user_id=agent.created_by_user_id,
                )
            )

    asyncio.run(publish())
    return public_id


def authorize(client: TestClient, workspace_id: str, public_agent_id: str) -> str:
    started = client.post(
        f"/api/v1/workspaces/{workspace_id}/channels/zalo/oauth/start",
        json={"agent_public_id": public_agent_id},
        headers=csrf_headers(client),
    )
    assert started.status_code == 200, started.text
    query = parse_qs(urlsplit(started.json()["authorization_url"]).query)
    assert query["app_id"] == [APP_ID]
    assert len(query["code_challenge"][0]) == 43
    return query["state"][0]


def complete_authorization(client: TestClient, state: str) -> None:
    callback = client.get(
        "/api/v1/channels/zalo/oauth/callback",
        params={"state": state, "code": "authorization-code", "oa_id": "oa-123"},
        follow_redirects=False,
    )
    assert callback.status_code == 303, callback.text
    assert "channel=zalo&oauth=success" in callback.headers["location"]


def signed_webhook() -> tuple[bytes, str]:
    timestamp = int(datetime.now(UTC).timestamp() * 1000)
    raw = json.dumps(
        {
            "app_id": APP_ID,
            "sender": {"id": "zalo-user-456"},
            "recipient": {"id": "oa-123"},
            "event_name": "user_send_text",
            "message": {"text": "Xin chào", "msg_id": "zalo-inbound-1"},
            "timestamp": timestamp,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    signature = hashlib.sha256(
        APP_ID.encode() + raw + str(timestamp).encode() + WEBHOOK_SECRET.encode()
    ).hexdigest()
    return raw, signature


def test_zalo_attachment_event_normalizes_without_trusting_provider_html() -> None:
    timestamp = int(datetime.now(UTC).timestamp() * 1000)
    raw = json.dumps(
        {
            "app_id": APP_ID,
            "sender": {"id": "zalo-user-456"},
            "recipient": {"id": "oa-123"},
            "event_name": "user_send_image",
            "message": {
                "msg_id": "zalo-image-1",
                "attachments": [
                    {
                        "type": "image",
                        "payload": {
                            "id": "image-123",
                            "url": "https://photo.zalo.example/image.jpg",
                        },
                    }
                ],
            },
            "timestamp": timestamp,
        },
        separators=(",", ":"),
    ).encode()
    signature = hashlib.sha256(
        APP_ID.encode() + raw + str(timestamp).encode() + WEBHOOK_SECRET.encode()
    ).hexdigest()

    events = ZaloWebhookAdapter(app_id=APP_ID, webhook_secret=WEBHOOK_SECRET).verify_and_normalize(
        raw_body=raw,
        headers={"x-zevent-signature": signature},
    )

    assert events[0].message.attachments[0].kind == "image"
    assert events[0].message.attachments[0].provider_media_id == "image-123"
    assert events[0].message.attachments[0].source_url == "https://photo.zalo.example/image.jpg"


def test_zalo_oauth_webhook_and_cross_workspace_isolation(app_factory: AppFactory) -> None:
    app, sessions, vault, gateway = app_factory()
    with TestClient(app) as client:
        workspace = register_workspace(client, email="owner@example.com", slug="zalo-shop")
        agent_id = create_published_agent(client, sessions, workspace["id"])
        state = authorize(client, workspace["id"], agent_id)
        assert len(gateway.exchange_verifiers) == 0

        complete_authorization(client, state)
        assert len(gateway.exchange_verifiers) == 1
        replay = client.get(
            "/api/v1/channels/zalo/oauth/callback",
            params={"state": state, "code": "authorization-code", "oa_id": "oa-123"},
            follow_redirects=False,
        )
        assert "oauth=error" in replay.headers["location"]

        listed = client.get(f"/api/v1/workspaces/{workspace['id']}/channels/zalo")
        assert listed.status_code == 200
        connection = listed.json()["items"][0]
        assert connection["webhook_configured"] is False

        configured = client.put(
            f"/api/v1/workspaces/{workspace['id']}/channels/zalo/{connection['id']}/webhook-secret",
            json={"webhook_secret": WEBHOOK_SECRET},
            headers=csrf_headers(client),
        )
        assert configured.status_code == 200, configured.text
        assert configured.json()["health_state"] == "healthy"
        assert configured.json()["webhook_configured"] is True

        raw, signature = signed_webhook()
        rejected = client.post(
            "/api/v1/webhooks/zalo",
            content=raw,
            headers={"content-type": "application/json", "x-zevent-signature": "0" * 64},
        )
        assert rejected.status_code == 401
        delivered = client.post(
            "/api/v1/webhooks/zalo",
            content=raw,
            headers={"content-type": "application/json", "x-zevent-signature": signature},
        )
        assert delivered.status_code == 200, delivered.text

        second_workspace = client.post(
            "/api/v1/workspaces",
            json={"slug": "other-shop", "display_name": "Other shop"},
            headers=csrf_headers(client),
        ).json()
        cross_workspace = client.post(
            f"/api/v1/workspaces/{second_workspace['id']}/channels/zalo/{connection['id']}/health",
            headers=csrf_headers(client),
        )
        assert cross_workspace.status_code == 404

    async def verify_persistence() -> None:
        async with sessions() as session:
            assert await session.scalar(select(func.count(ChannelConnection.id))) == 1
            assert await session.scalar(select(func.count(ChannelOAuthAttempt.id))) == 1
            assert await session.scalar(select(func.count(ChannelWebhookEvent.id))) == 1
            assert await session.scalar(select(func.count(ConversationMessage.id))) == 1
            assert await session.scalar(select(func.count(ChannelResponseJob.id))) == 1

        async with sessions() as session:
            claim = await ChannelResponseService(
                session,
                Settings(
                    app_env="test",
                    jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                ),
            ).claim()
            assert claim is not None
            assert claim.provider == "zalo"

    asyncio.run(verify_persistence())
    assert any(WEBHOOK_SECRET in value for value in vault.values.values())

    async def verify_refresh_rotation() -> None:
        async with sessions() as session:
            connection = (
                await session.scalars(
                    select(ChannelConnection).where(ChannelConnection.provider == "zalo")
                )
            ).one()
            assert connection.credential_ref is not None
            bundle = decode_bundle(vault.values[connection.credential_ref])
            vault.values[connection.credential_ref] = encode_bundle(
                type(bundle)(
                    access_token=bundle.access_token,
                    refresh_token=bundle.refresh_token,
                    expires_at=datetime.now(UTC) - timedelta(seconds=1),
                    webhook_secret=bundle.webhook_secret,
                )
            )
            connection_id = connection.id
        manager = cast(ZaloTokenManager, app.state.zalo_token_manager)
        assert await manager.access_token(connection_id=connection_id) == "refreshed-access"
        assert await manager.access_token(connection_id=connection_id) == "refreshed-access"

    asyncio.run(verify_refresh_rotation())
    assert gateway.refreshes == 1


def test_zalo_callback_is_bound_to_initiating_user(app_factory: AppFactory) -> None:
    app, sessions, _, gateway = app_factory()
    with TestClient(app) as owner:
        workspace = register_workspace(owner, email="owner@example.com", slug="owner-shop")
        agent_id = create_published_agent(owner, sessions, workspace["id"])
        state = authorize(owner, workspace["id"], agent_id)

    with TestClient(app) as attacker:
        register_workspace(attacker, email="attacker@example.com", slug="attacker-shop")
        response = attacker.get(
            "/api/v1/channels/zalo/oauth/callback",
            params={"state": state, "code": "authorization-code", "oa_id": "oa-123"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "oauth=error" in response.headers["location"]
    assert gateway.exchange_verifiers == []
