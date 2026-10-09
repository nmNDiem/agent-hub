import asyncio
import hashlib
import hmac
import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
from agent_hub_api.agents.runtime import (
    AgentConversationTurn,
    AgentExecutionContext,
    AgentRuntimeUsage,
    GroundedAgentResponse,
)
from agent_hub_api.channels.models import (
    ChannelConnection,
    ChannelDeliveryReceipt,
    ChannelInboundMedia,
    ChannelResponseJob,
    ChannelThreadMapping,
    OutboundDelivery,
)
from agent_hub_api.channels.service import ChannelService, DeliveryRunner
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.facebook.contracts import FacebookPageIdentity
from agent_hub_api.facebook.media import FacebookMediaDownloader, FacebookMediaLimits
from agent_hub_api.facebook.outbound import FacebookOutboundAdapter
from agent_hub_api.facebook.responses import (
    ClaimedResponseJob,
    FacebookResponseError,
    FacebookResponseRunner,
    FacebookResponseService,
)
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
    def __call__(
        self,
    ) -> tuple[
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
                    catalog_scope_json={"location_ids": None, "collection_ids": None},
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


def signed_attachment_payload(
    *, message_id: str, timestamp: int, kind: str, url: str | None = None
) -> tuple[bytes, str]:
    attachment_payload = {} if url is None else {"url": url}
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
                            "message": {
                                "mid": message_id,
                                "attachments": [{"type": kind, "payload": attachment_payload}],
                            },
                        }
                    ],
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    signature = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, signature


def test_image_and_opt_out_events_create_one_durable_job_without_duplicate_spend(
    app_factory: AppFactory,
) -> None:
    app, session_factory, _, _ = app_factory()
    with TestClient(app) as client:
        workspace = register_workspace(client, email="fb-policy@example.com", slug="fb-policy")
        agent_id = create_published_agent(client, session_factory, workspace["id"])
        connected = client.post(
            f"/api/v1/workspaces/{workspace['id']}/channels/facebook",
            json={"agent_public_id": agent_id, "page_access_token": "page-token-secret"},
            headers=csrf_headers(client),
        )
        assert connected.status_code == 201, connected.text

        image_body, image_signature = signed_attachment_payload(
            message_id="mid-image",
            timestamp=1_800_000_000_000,
            kind="image",
            url="https://scontent.xx.fbcdn.net/private/image.jpg?token=secret",
        )
        for _ in range(2):
            response = client.post(
                "/api/v1/webhooks/facebook",
                content=image_body,
                headers={"x-hub-signature-256": image_signature},
            )
            assert response.status_code == 200, response.text

        stop_body, stop_signature = signed_payload(
            message_id="mid-stop", timestamp=1_800_000_001_000, text="STOP"
        )
        assert (
            client.post(
                "/api/v1/webhooks/facebook",
                content=stop_body,
                headers={"x-hub-signature-256": stop_signature},
            ).status_code
            == 200
        )
        ignored_body, ignored_signature = signed_payload(
            message_id="mid-ignored", timestamp=1_800_000_002_000, text="Xin chào"
        )
        assert (
            client.post(
                "/api/v1/webhooks/facebook",
                content=ignored_body,
                headers={"x-hub-signature-256": ignored_signature},
            ).status_code
            == 200
        )
        start_body, start_signature = signed_payload(
            message_id="mid-start", timestamp=1_800_000_003_000, text="BẮT ĐẦU"
        )
        assert (
            client.post(
                "/api/v1/webhooks/facebook",
                content=start_body,
                headers={"x-hub-signature-256": start_signature},
            ).status_code
            == 200
        )
        audio_body, audio_signature = signed_attachment_payload(
            message_id="mid-audio",
            timestamp=1_800_000_004_000,
            kind="audio",
        )
        assert (
            client.post(
                "/api/v1/webhooks/facebook",
                content=audio_body,
                headers={"x-hub-signature-256": audio_signature},
            ).status_code
            == 200
        )

        async def assert_policy() -> None:
            async with session_factory() as session:
                jobs = list(await session.scalars(select(ChannelResponseJob)))
                assert len(jobs) == 2  # image and exact opt-in; duplicate/opt-out add none
                media = list(
                    await session.scalars(
                        select(ChannelInboundMedia).order_by(ChannelInboundMedia.id)
                    )
                )
                assert [(item.kind, item.state) for item in media] == [
                    ("image", "pending"),
                    ("audio", "unsupported"),
                ]
                assert media[0].source_url is not None
                assert media[1].source_url is None
                thread = (await session.scalars(select(ChannelThreadMapping))).one()
                assert thread.automation_state == "opted_in"

        asyncio.run(assert_policy())

        class CleanupStorage:
            async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None:
                raise AssertionError("cleanup must not upload media")

            async def download(self, *, object_key: str, max_bytes: int) -> bytes:
                raise AssertionError("cleanup must not download media")

            async def delete(self, *, object_key: str) -> None:
                raise AssertionError("pending media has no stored object")

        async def assert_expired_media_cleanup() -> None:
            async with session_factory() as session, session.begin():
                media = (
                    await session.scalars(
                        select(ChannelInboundMedia).where(ChannelInboundMedia.kind == "image")
                    )
                ).one()
                media.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            async with session_factory() as session:
                cleaned = await FacebookResponseService(
                    session,
                    Settings(
                        app_env="test",
                        jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                    ),
                ).cleanup_once(CleanupStorage())
                assert cleaned is True
            async with session_factory() as session:
                media = (
                    await session.scalars(
                        select(ChannelInboundMedia).where(ChannelInboundMedia.kind == "image")
                    )
                ).one()
                assert media.state == "deleted"
                assert media.source_url is None

        asyncio.run(assert_expired_media_cleanup())


def test_reauthorization_rotates_credential_and_rejects_cross_workspace_access(
    app_factory: AppFactory,
) -> None:
    app, session_factory, vault, _ = app_factory()
    with TestClient(app) as owner, TestClient(app) as outsider:
        workspace = register_workspace(owner, email="fb-reauth@example.com", slug="fb-reauth")
        other = register_workspace(outsider, email="fb-other@example.com", slug="fb-other")
        agent_id = create_published_agent(owner, session_factory, workspace["id"])
        connected = owner.post(
            f"/api/v1/workspaces/{workspace['id']}/channels/facebook",
            json={"agent_public_id": agent_id, "page_access_token": "page-token-secret"},
            headers=csrf_headers(owner),
        )
        connection_id = cast(int, connected.json()["id"])
        old_ref = next(iter(vault.values))

        denied = outsider.post(
            f"/api/v1/workspaces/{workspace['id']}/channels/facebook/{connection_id}/reauthorize",
            json={"page_access_token": "page-token-secret"},
            headers=csrf_headers(outsider),
        )
        assert denied.status_code == 404
        own_missing = outsider.post(
            f"/api/v1/workspaces/{other['id']}/channels/facebook/{connection_id}/reauthorize",
            json={"page_access_token": "page-token-secret"},
            headers=csrf_headers(outsider),
        )
        assert own_missing.status_code == 404

        rotated = owner.post(
            f"/api/v1/workspaces/{workspace['id']}/channels/facebook/{connection_id}/reauthorize",
            json={"page_access_token": "page-token-secret"},
            headers=csrf_headers(owner),
        )
        assert rotated.status_code == 200, rotated.text
        assert rotated.json()["health_state"] == "healthy"
        assert "page_access_token" not in rotated.text
        assert old_ref in vault.revoked
        assert len(vault.values) == 1


def test_duplicate_webhook_runs_grounded_response_and_queues_delivery_once(
    app_factory: AppFactory,
) -> None:
    app, session_factory, _, _ = app_factory()

    class FakeRuntime:
        def __init__(self) -> None:
            self.calls = 0

        async def run_with_context(
            self,
            context: AgentExecutionContext,
            *,
            question: str,
            history: tuple[AgentConversationTurn, ...] = (),
        ) -> GroundedAgentResponse:
            del context, history
            self.calls += 1
            assert question == "Tư vấn giúp mình"
            return GroundedAgentResponse(
                text="Mình có thể hỗ trợ.",
                product_cards=[],
                sources=[],
                usage=AgentRuntimeUsage(
                    model_calls=1,
                    tool_calls=0,
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                ),
            )

    class FakeStorage:
        async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None:
            raise AssertionError("text response must not upload media")

        async def download(self, *, object_key: str, max_bytes: int) -> bytes:
            raise AssertionError("text response must not download media")

        async def delete(self, *, object_key: str) -> None:
            return None

    runtime = FakeRuntime()
    with TestClient(app) as client:
        workspace = register_workspace(client, email="fb-runtime@example.com", slug="fb-runtime")
        agent_id = create_published_agent(client, session_factory, workspace["id"])
        assert (
            client.post(
                f"/api/v1/workspaces/{workspace['id']}/channels/facebook",
                json={"agent_public_id": agent_id, "page_access_token": "page-token-secret"},
                headers=csrf_headers(client),
            ).status_code
            == 201
        )
        body, signature = signed_payload(
            message_id="mid-runtime",
            timestamp=int(datetime.now(UTC).timestamp() * 1000),
            text="Tư vấn giúp mình",
        )
        for _ in range(2):
            assert (
                client.post(
                    "/api/v1/webhooks/facebook",
                    content=body,
                    headers={"x-hub-signature-256": signature},
                ).status_code
                == 200
            )

    async def run_and_assert() -> None:
        settings = Settings(
            app_env="test",
            jwt_signing_key="test-signing-key-with-at-least-32-bytes",
        )
        async with session_factory() as session:
            worked = await FacebookResponseRunner(
                FacebookResponseService(session, settings),
                runtime_factory=lambda _: runtime,
                media_downloader=FacebookMediaDownloader(
                    FacebookMediaLimits(
                        max_bytes=1_000,
                        max_pixels=1_000,
                        max_redirects=1,
                        timeout_seconds=1,
                        allowed_hosts=("fbcdn.net",),
                    )
                ),
                storage=FakeStorage(),
                vision=None,
            ).run_once()
            assert worked is True
        async with session_factory() as session:
            jobs = list(await session.scalars(select(ChannelResponseJob)))
            assert len(jobs) == 1
            assert jobs[0].state == "completed"
            assert jobs[0].outbound_message_id is not None
            assert await session.scalar(select(func.count(OutboundDelivery.id))) == 1
            assert (
                await session.scalar(
                    select(func.count(ConversationMessage.id)).where(
                        ConversationMessage.direction == "outbound"
                    )
                )
                == 1
            )

        async with session_factory() as session:
            claimed_delivery = await ChannelService(session).claim_delivery(
                now=datetime.now(UTC) + timedelta(hours=25)
            )
            assert claimed_delivery is None
        async with session_factory() as session:
            delivery = (await session.scalars(select(OutboundDelivery))).one()
            assert delivery.state == "failed_terminal"
            assert delivery.safe_error_code == "FACEBOOK_RESPONSE_WINDOW_EXPIRED"

        async with session_factory() as session, session.begin():
            job = (await session.scalars(select(ChannelResponseJob))).one()
            thread = (await session.scalars(select(ChannelThreadMapping))).one()
            conversation = await session.get(Conversation, job.conversation_id)
            assert conversation is not None
            job.state = "running"
            job.lease_token = "current-response-lease"
            job.lease_expires_at = datetime.now(UTC) + timedelta(minutes=1)
            claim = ClaimedResponseJob(
                id=job.id,
                workspace_id=job.workspace_id,
                connection_id=job.connection_id,
                conversation_id=job.conversation_id,
                inbound_message_id=job.inbound_message_id,
                revision_id=conversation.revision_id,
                agent_id=conversation.agent_id,
                thread_mapping_id=thread.id,
                lease_token="current-response-lease",
                question="Tư vấn giúp mình",
                history=(),
                media_ids=(),
            )
        async with session_factory() as session:
            with pytest.raises(FacebookResponseError, match="STALE_RESPONSE_LEASE"):
                await FacebookResponseService(session, settings).fail(
                    replace(claim, lease_token="stale-response-lease"),
                    safe_code="TEST_FAILURE",
                    retryable=False,
                )
        async with session_factory() as session, session.begin():
            job = (await session.scalars(select(ChannelResponseJob))).one()
            assert job.lease_token == "current-response-lease"
            job.state = "completed"
            job.lease_token = None
            job.lease_expires_at = None

    asyncio.run(run_and_assert())
    assert runtime.calls == 1


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

        denied = owner_b.get(f"/api/v1/workspaces/{workspace_a['id']}/channels/facebook")
        assert denied.status_code == 404
        own_empty = owner_b.get(f"/api/v1/workspaces/{workspace_b['id']}/channels/facebook")
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
        first_body, first_signature = signed_payload(message_id="mid-1", timestamp=newest_timestamp)
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
