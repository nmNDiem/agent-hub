import asyncio
import hashlib
import hmac
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
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
    ChannelDeliveryReceipt,
    ChannelThreadMapping,
    OutboundDelivery,
)
from agent_hub_api.channels.service import ChannelService, DeliveryRunner
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.facebook.contracts import FacebookPageIdentity
from agent_hub_api.facebook.outbound import FacebookOutboundAdapter
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.main import create_app
from agent_hub_api.models import Base

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"
APP_SECRET = "facebook-test-app-secret"
VERIFY_TOKEN = "facebook-test-verify-token"


class FakeVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.revoked: list[str] = []

    async def store(self, *, workspace_id: UUID, plaintext: str) -> str:
        reference = f"fake:{workspace_id}:{len(self.values) + 1}"
        self.values[reference] = plaintext
        return reference

    async def resolve(self, credential_ref: str) -> str:
        return self.values[credential_ref]

    async def revoke(self, credential_ref: str) -> None:
        self.values.pop(credential_ref, None)
        self.revoked.append(credential_ref)


class FakeGraph:
    def __init__(self) -> None:
        self.identity = FacebookPageIdentity(page_id="page-123", name="Example Page")
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.sent: list[tuple[str, str, str]] = []

    async def validate_page_token(self, page_access_token: str) -> FacebookPageIdentity:
        assert page_access_token == "page-token-secret"
        return self.identity

    async def subscribe_page(self, page_id: str, page_access_token: str) -> None:
        assert page_access_token == "page-token-secret"
        self.subscribed.append(page_id)

    async def unsubscribe_page(self, page_id: str, page_access_token: str) -> None:
        assert page_access_token == "page-token-secret"
        self.unsubscribed.append(page_id)

    async def send_text(
        self,
        *,
        page_id: str,
        recipient_id: str,
        text: str,
        page_access_token: str,
    ) -> str:
        assert page_access_token == "page-token-secret"
        self.sent.append((page_id, recipient_id, text))
        return "provider-mid-1"


class AppFactory(Protocol):
    def __call__(self) -> tuple[
        FastAPI,
        async_sessionmaker[AsyncSession],
        FakeVault,
        FakeGraph,
    ]: ...


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    resources: list[AsyncEngine] = []

    def build() -> tuple[
        FastAPI,
        async_sessionmaker[AsyncSession],
        FakeVault,
        FakeGraph,
    ]:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'facebook.db'}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        vault = FakeVault()
        graph = FakeGraph()
        app = create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                facebook_app_secret=APP_SECRET,
                facebook_webhook_verify_token=VERIFY_TOKEN,
                facebook_webhook_max_bytes=2048,
            ),
            session_factory=session_factory,
            credential_vault=vault,
            facebook_graph_gateway=graph,
        )
        resources.append(engine)
        return app, session_factory, vault, graph

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


def create_published_agent(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    workspace_id: str,
) -> str:
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/agents",
        json={"name": "Facebook agent"},
        headers=csrf_headers(client),
    )
    assert created.status_code == 201, created.text
    public_id = cast(str, created.json()["public_id"])

    async def publish() -> None:
        async with session_factory() as session, session.begin():
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
                    catalog_scope_json={},
                    knowledge_base_ids_json=[],
                    widget_config_json={},
                    config_hash="a" * 64,
                    created_by_user_id=agent.created_by_user_id,
                )
            )

    asyncio.run(publish())
    return public_id


def signed_payload(*, message_id: str, timestamp: int, text: str = "Xin chào") -> tuple[bytes, str]:
    body = json.dumps(
        {
            "object": "page",
            "entry": [
                {
                    "id": "page-123",
                    "messaging": [
                        {
                            "sender": {"id": "psid-456"},
                            "recipient": {"id": "page-123"},
                            "timestamp": timestamp,
                            "message": {"mid": message_id, "text": text},
                        }
                    ],
                }
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    signature = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, signature


def signed_delivery_payload(*, message_id: str, watermark: int) -> tuple[bytes, str]:
    body = json.dumps(
        {
            "object": "page",
            "entry": [
                {
                    "id": "page-123",
                    "messaging": [
                        {
                            "sender": {"id": "psid-456"},
                            "recipient": {"id": "page-123"},
                            "delivery": {"mids": [message_id], "watermark": watermark},
                        }
                    ],
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    signature = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, signature


def test_connection_and_verified_webhook_are_scoped_deduplicated_and_reorder_safe(
    app_factory: AppFactory,
) -> None:
    app, session_factory, vault, graph = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        workspace_a = register_workspace(owner_a, email="fb-a@example.com", slug="fb-a")
        workspace_b = register_workspace(owner_b, email="fb-b@example.com", slug="fb-b")
        agent_id = create_published_agent(owner_a, session_factory, workspace_a["id"])

        connected = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/channels/facebook",
            json={"agent_public_id": agent_id, "page_access_token": "page-token-secret"},
            headers=csrf_headers(owner_a),
        )
        assert connected.status_code == 201, connected.text
        connection = connected.json()
        assert connection["external_account_id"] == "page-123"
        assert connection["health_state"] == "healthy"
        assert "token" not in connected.text.casefold()
        assert list(vault.values.values()) == ["page-token-secret"]
        assert graph.subscribed == ["page-123"]

        denied = owner_b.get(
            f"/api/v1/workspaces/{workspace_a['id']}/channels/facebook"
        )
        assert denied.status_code == 404
        own_empty = owner_b.get(
            f"/api/v1/workspaces/{workspace_b['id']}/channels/facebook"
        )
        assert own_empty.status_code == 200
        assert own_empty.json() == {"items": []}

        challenge = owner_a.get(
            "/api/v1/webhooks/facebook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "challenge-value",
            },
        )
        assert challenge.status_code == 200
        assert challenge.text == "challenge-value"

        newest_timestamp = 1_800_000_000_000
        first_body, first_signature = signed_payload(
            message_id="mid-1", timestamp=newest_timestamp
        )
        invalid = owner_a.post(
            "/api/v1/webhooks/facebook",
            content=first_body,
            headers={"x-hub-signature-256": "sha256=" + "0" * 64},
        )
        assert invalid.status_code == 401

        for _ in range(2):
            accepted = owner_a.post(
                "/api/v1/webhooks/facebook",
                content=first_body,
                headers={"x-hub-signature-256": first_signature},
            )
            assert accepted.status_code == 200, accepted.text

        older_body, older_signature = signed_payload(
            message_id="mid-2", timestamp=newest_timestamp - 1_000
        )
        reordered = owner_a.post(
            "/api/v1/webhooks/facebook",
            content=older_body,
            headers={"x-hub-signature-256": older_signature},
        )
        assert reordered.status_code == 200, reordered.text

        async def assert_persisted() -> None:
            async with session_factory() as session:
                assert await session.scalar(select(func.count(ConversationMessage.id))) == 2
                thread = (await session.scalars(select(ChannelThreadMapping))).one()
                assert thread.last_seen_at == datetime.fromtimestamp(
                    newest_timestamp / 1000, tz=UTC
                ).replace(tzinfo=None)

        asyncio.run(assert_persisted())

        async def queue_outbound() -> int:
            async with session_factory() as session, session.begin():
                conversation = (await session.scalars(select(Conversation))).one()
                thread = (await session.scalars(select(ChannelThreadMapping))).one()
                message = ConversationMessage(
                    workspace_id=conversation.workspace_id,
                    conversation_id=conversation.id,
                    sequence_no=3,
                    actor="assistant",
                    direction="outbound",
                    text="Phản hồi Facebook",
                    status="completed",
                    completed_at=datetime.now(UTC),
                )
                session.add(message)
                await session.flush()
                message_id = message.id
                workspace_id = conversation.workspace_id
                connection_id = conversation.channel_connection_id
                thread_id = thread.id
            async with session_factory() as session:
                delivery = await ChannelService(session).queue_delivery(
                    workspace_id=workspace_id,
                    connection_id=connection_id,
                    thread_mapping_id=thread_id,
                    message_id=message_id,
                    idempotency_key="facebook-response-1",
                )
                return delivery.id

        delivery_id = asyncio.run(queue_outbound())
        receipt_watermark = newest_timestamp + 2_000
        receipt_body, receipt_signature = signed_delivery_payload(
            message_id="provider-mid-1", watermark=receipt_watermark
        )
        early_receipt = owner_a.post(
            "/api/v1/webhooks/facebook",
            content=receipt_body,
            headers={"x-hub-signature-256": receipt_signature},
        )
        assert early_receipt.status_code == 200, early_receipt.text

        async def deliver() -> None:
            async with session_factory() as session:
                worked = await DeliveryRunner(
                    ChannelService(session),
                    {"facebook": FacebookOutboundAdapter(vault=vault, graph=graph)},
                ).run_once()
                assert worked is True

        asyncio.run(deliver())
        duplicate_receipt = owner_a.post(
            "/api/v1/webhooks/facebook",
            content=receipt_body,
            headers={"x-hub-signature-256": receipt_signature},
        )
        assert duplicate_receipt.status_code == 200

        async def assert_delivery() -> None:
            async with session_factory() as session:
                delivery = await session.get(OutboundDelivery, delivery_id)
                assert delivery is not None
                assert delivery.state == "delivered"
                assert delivery.provider_message_id == "provider-mid-1"
                assert delivery.accepted_at is not None
                assert delivery.delivered_at == datetime.fromtimestamp(
                    receipt_watermark / 1000, tz=UTC
                ).replace(tzinfo=None)
                assert await session.scalar(select(func.count(ChannelDeliveryReceipt.id))) == 1

        asyncio.run(assert_delivery())
        assert graph.sent == [("page-123", "psid-456", "Phản hồi Facebook")]

        health = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/channels/facebook/{connection['id']}/health",
            headers=csrf_headers(owner_a),
        )
        assert health.status_code == 200, health.text

        revoked = owner_a.delete(
            f"/api/v1/workspaces/{workspace_a['id']}/channels/facebook/{connection['id']}",
            headers=csrf_headers(owner_a),
        )
        assert revoked.status_code == 204, revoked.text
        assert vault.values == {}
        assert graph.unsubscribed == ["page-123"]

        after_body, after_signature = signed_payload(
            message_id="mid-3", timestamp=newest_timestamp + 1_000
        )
        after_revoke = owner_a.post(
            "/api/v1/webhooks/facebook",
            content=after_body,
            headers={"x-hub-signature-256": after_signature},
        )
        assert after_revoke.status_code == 200

        async def assert_revoked() -> None:
            async with session_factory() as session:
                stored = await session.get(ChannelConnection, connection["id"])
                assert stored is not None
                assert stored.lifecycle_state == "revoked"
                assert stored.credential_ref is None
                assert await session.scalar(select(func.count(ConversationMessage.id))) == 3

        asyncio.run(assert_revoked())


def test_webhook_rejects_bad_challenge_and_oversized_body(app_factory: AppFactory) -> None:
    app, _, _, _ = app_factory()
    with TestClient(app) as client:
        challenge = client.get(
            "/api/v1/webhooks/facebook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token-value",
                "hub.challenge": "challenge",
            },
        )
        assert challenge.status_code == 403

        oversized = b"x" * 2049
        response = client.post(
            "/api/v1/webhooks/facebook",
            content=oversized,
            headers={"x-hub-signature-256": "sha256=" + "0" * 64},
        )
        assert response.status_code == 413
