import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.agents.runtime import (
    AgentConversationTurn,
    AgentExecutionContext,
    GroundedAgentResponse,
)
from agent_hub_api.core.config import Settings
from agent_hub_api.identity.models import User
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.main import create_app
from agent_hub_api.models import Base
from agent_hub_api.telemetry.service import month_bounds
from agent_hub_api.workspaces.models import WorkspaceMember

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"
ABUSE_KEY = "widget-test-abuse-key-with-at-least-32-bytes"


class FakeRuntime:
    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self,
        *,
        workspace_id: UUID,
        public_agent_id: UUID,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse:
        del workspace_id, public_agent_id, question, history
        return await self._response()

    async def run_with_context(
        self,
        context: AgentExecutionContext,
        *,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse:
        del context, question, history
        return await self._response()

    async def _response(self) -> GroundedAgentResponse:
        self.calls += 1
        return GroundedAgentResponse.model_validate(
            {
                "text": "Phản hồi đã được kiểm chứng.",
                "product_cards": [],
                "sources": [],
                "usage": {
                    "model_calls": 2,
                    "tool_calls": 1,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
            }
        )


class AppFactory(Protocol):
    def __call__(self, runtime: FakeRuntime, *, limit: int = 1_000) -> FastAPI: ...


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    engines: list[AsyncEngine] = []

    def build(runtime: FakeRuntime, *, limit: int = 1_000) -> FastAPI:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / f'conversations-{len(engines)}.db'}"
        )

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        engines.append(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        return create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                widget_public_base_url="http://127.0.0.1:4173",
                widget_abuse_hash_key=ABUSE_KEY,
                workspace_monthly_generated_turn_limit=limit,
            ),
            session_factory=session_factory,
            agent_runtime_factory=lambda _: runtime,
        )

    yield build

    async def dispose() -> None:
        for engine in engines:
            await engine.dispose()

    asyncio.run(dispose())


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"x-csrf-token": token, "origin": ORIGIN}


def publish_agent(client: TestClient, email: str, slug: str) -> dict[str, str]:
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD},
            headers={"origin": ORIGIN},
        ).status_code
        == 201
    )
    workspace = client.post(
        "/api/v1/workspaces",
        json={
            "slug": slug,
            "display_name": slug,
            "timezone": "Asia/Ho_Chi_Minh",
        },
        headers=csrf_headers(client),
    ).json()
    agent = client.post(
        f"/api/v1/workspaces/{workspace['id']}/agents",
        json={"name": "Trợ lý", "safe_instructions": "Chỉ dùng dữ liệu thật"},
        headers=csrf_headers(client),
    ).json()
    base = f"/api/v1/workspaces/{workspace['id']}/agents/{agent['public_id']}"
    assert (
        client.put(
            f"{base}/widget",
            json={
                "display_name": "Trợ lý",
                "greeting": "Xin chào",
                "brand_color": "#0F8F87",
                "launcher_position": "right",
                "allowed_origins": [ORIGIN],
                "handoff_url": None,
                "handoff_label": None,
            },
            headers=csrf_headers(client),
        ).status_code
        == 200
    )
    assert client.post(f"{base}/publish", headers=csrf_headers(client)).status_code == 200
    return {"workspace_id": workspace["id"], "agent_id": agent["public_id"], "base": base}


def visitor(client: TestClient, agent_id: str) -> tuple[str, str]:
    session = client.post(f"/api/v1/widget/{agent_id}/sessions", headers={"origin": ORIGIN})
    token = session.json()["access_token"]
    headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
    conversation = client.post("/api/v1/widget/conversations", headers=headers)
    return token, conversation.json()["public_id"]


def send(client: TestClient, token: str, conversation_id: str, key: str) -> Response:
    return client.post(
        f"/api/v1/widget/conversations/{conversation_id}/messages",
        json={"message": f"Câu hỏi {key}"},
        headers={
            "origin": ORIGIN,
            "authorization": f"Bearer {token}",
            "idempotency-key": key,
        },
    )


def test_month_bounds_follow_the_workspace_timezone() -> None:
    started_at, ends_at = month_bounds("Asia/Ho_Chi_Minh", datetime(2026, 10, 15, 12, tzinfo=UTC))

    assert started_at == datetime(2026, 9, 30, 17, tzinfo=UTC)
    assert ends_at == datetime(2026, 10, 31, 17, tzinfo=UTC)


def test_conversation_dashboard_usage_and_quota_are_scoped_and_real(
    app_factory: AppFactory,
) -> None:
    runtime = FakeRuntime()
    app = app_factory(runtime, limit=2)
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        shop_a = publish_agent(owner_a, "owner-a@example.com", "shop-a")
        shop_b = publish_agent(owner_b, "owner-b@example.com", "shop-b")
        token_a1, conversation_a1 = visitor(owner_a, shop_a["agent_id"])
        token_a2, conversation_a2 = visitor(owner_a, shop_a["agent_id"])
        sent_a1 = send(owner_a, token_a1, conversation_a1, "turn-a-0001")
        sent_a2 = send(owner_a, token_a2, conversation_a2, "turn-a-0002")
        assert sent_a1.status_code == 200, sent_a1.text
        assert sent_a2.status_code == 200, sent_a2.text

        first = owner_a.get(f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations?limit=1")
        assert first.status_code == 200
        assert first.headers["cache-control"] == "no-store"
        assert first.json()["next_cursor"] is not None
        second = owner_a.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations",
            params={"limit": 1, "cursor": first.json()["next_cursor"]},
        )
        listed_ids = {
            first.json()["items"][0]["public_id"],
            second.json()["items"][0]["public_id"],
        }
        assert listed_ids == {conversation_a1, conversation_a2}
        detail = owner_a.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations/{conversation_a1}"
        )
        assert detail.status_code == 200
        assert len(detail.json()["messages"]) == 2
        serialized = detail.text
        assert "conversation_id" not in serialized
        assert "object_key" not in serialized
        assert "request_key" not in serialized

        usage = owner_a.get(f"/api/v1/workspaces/{shop_a['workspace_id']}/usage")
        assert usage.status_code == 200
        assert usage.json()["generated_turns"] == 2
        assert usage.json()["generation_model_calls"] == 4
        assert usage.json()["total_tokens"] == 30
        dashboard = owner_a.get(f"/api/v1/workspaces/{shop_a['workspace_id']}/dashboard?days=7")
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["total_conversations"] == 2
        assert dashboard.json()["assistant_messages"] == 2
        assert dashboard.json()["active_agents"] == 1
        assert sum(item["conversations"] for item in dashboard.json()["activity"]) == 2

        token_a3, conversation_a3 = visitor(owner_a, shop_a["agent_id"])
        denied = send(owner_a, token_a3, conversation_a3, "turn-over-quota")
        assert denied.status_code == 429
        assert denied.json()["error"]["code"] == "WORKSPACE_MONTHLY_QUOTA_EXCEEDED"
        assert runtime.calls == 2
        assert (
            owner_b.get(f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations").status_code
            == 404
        )
        assert (
            owner_a.get(f"/api/v1/workspaces/{shop_b['workspace_id']}/dashboard").status_code == 404
        )

        session_factory = cast(async_sessionmaker[AsyncSession], app.state.session_factory)

        async def set_owner_b_role(role: str) -> None:
            async with session_factory() as session, session.begin():
                user = await session.scalar(
                    select(User).where(User.normalized_email == "owner-b@example.com")
                )
                assert user is not None
                membership = await session.scalar(
                    select(WorkspaceMember).where(
                        WorkspaceMember.workspace_id == UUID(shop_a["workspace_id"]),
                        WorkspaceMember.user_id == user.id,
                    )
                )
                if membership is None:
                    session.add(
                        WorkspaceMember(
                            workspace_id=UUID(shop_a["workspace_id"]),
                            user_id=user.id,
                            role=role,
                        )
                    )
                else:
                    membership.role = role

        asyncio.run(set_owner_b_role("admin"))
        assert (
            owner_b.get(f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations").status_code
            == 200
        )
        asyncio.run(set_owner_b_role("member"))
        member_list = owner_b.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations"
        )
        assert member_list.status_code == 200
        assert conversation_a1 in {item["public_id"] for item in member_list.json()["items"]}
        member_options = owner_b.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/inbox/members"
        ).json()["items"]
        member_id = next(
            item["id"] for item in member_options if item["email"] == "owner-b@example.com"
        )
        member_detail_url = (
            f"/api/v1/workspaces/{shop_a['workspace_id']}"
            f"/conversations/{conversation_a1}"
        )
        member_detail = owner_b.get(member_detail_url).json()
        claim = owner_b.patch(
            f"{member_detail_url}/state",
            json={
                "state_version": member_detail["conversation"]["state_version"],
                "assigned_member_id": member_id,
            },
            headers=csrf_headers(owner_b),
        )
        assert claim.status_code == 204, claim.text
        claimed = owner_b.get(member_detail_url).json()
        clear_own_assignment = owner_b.patch(
            f"{member_detail_url}/state",
            json={
                "state_version": claimed["conversation"]["state_version"],
                "clear_assignment": True,
            },
            headers=csrf_headers(owner_b),
        )
        assert clear_own_assignment.status_code == 403
        assert (
            owner_b.get(f"/api/v1/workspaces/{shop_a['workspace_id']}/dashboard").status_code == 403
        )
        assert owner_b.get(f"/api/v1/workspaces/{shop_a['workspace_id']}/usage").status_code == 403

        assert (
            owner_a.delete(
                f"/api/v1/widget/conversations/{conversation_a1}",
                headers={"origin": ORIGIN, "authorization": f"Bearer {token_a1}"},
            ).status_code
            == 204
        )
        assert (
            owner_a.get(
                f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations/{conversation_a1}"
            ).status_code
            == 404
        )


def test_website_human_takeover_reply_and_tenant_guards(app_factory: AppFactory) -> None:
    runtime = FakeRuntime()
    app = app_factory(runtime)
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        shop_a = publish_agent(owner_a, "inbox-a@example.com", "inbox-a")
        shop_b = publish_agent(owner_b, "inbox-b@example.com", "inbox-b")
        token, conversation_id = visitor(owner_a, shop_a["agent_id"])
        assert send(owner_a, token, conversation_id, "before-handoff").status_code == 200
        assert runtime.calls == 1

        members = owner_a.get(f"/api/v1/workspaces/{shop_a['workspace_id']}/inbox/members")
        assert members.status_code == 200
        owner_member_id = members.json()["items"][0]["id"]
        detail = owner_a.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations/{conversation_id}"
        ).json()
        state_url = (
            f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations/{conversation_id}/state"
        )
        missing_csrf = owner_a.patch(
            state_url,
            json={
                "state_version": detail["conversation"]["state_version"],
                "handling_mode": "human",
            },
        )
        assert missing_csrf.status_code == 403
        takeover = owner_a.patch(
            state_url,
            json={
                "state_version": detail["conversation"]["state_version"],
                "handling_mode": "human",
                "assigned_member_id": owner_member_id,
            },
            headers=csrf_headers(owner_a),
        )
        assert takeover.status_code == 204, takeover.text
        stale = owner_a.patch(
            state_url,
            json={
                "state_version": detail["conversation"]["state_version"],
                "workflow_status": "pending",
            },
            headers=csrf_headers(owner_a),
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "STALE_CONVERSATION"

        conversation_url = (
            f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations/{conversation_id}"
        )
        assert owner_a.post(
            f"{conversation_url}/notes",
            json={"body": "Cần kiểm tra lại kích thước."},
            headers=csrf_headers(owner_a),
        ).status_code == 204
        assert owner_a.post(
            f"{conversation_url}/tags",
            json={"name": "Ưu tiên"},
            headers=csrf_headers(owner_a),
        ).status_code == 204
        enriched = owner_a.get(conversation_url).json()
        assert enriched["notes"][0]["body"] == "Cần kiểm tra lại kích thước."
        tag_id = enriched["conversation"]["tags"][0]["id"]
        filtered = owner_a.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations",
            params={"tag_id": tag_id},
        )
        assert [item["public_id"] for item in filtered.json()["items"]] == [conversation_id]

        waiting = send(owner_a, token, conversation_id, "after-handoff")
        assert waiting.status_code == 200
        assert "event: handoff.waiting" in waiting.text
        assert runtime.calls == 1

        reply_url = (
            f"/api/v1/workspaces/{shop_a['workspace_id']}/conversations/{conversation_id}/replies"
        )
        reply_headers = {**csrf_headers(owner_a), "idempotency-key": "human-reply-0001"}
        assert (
            owner_a.post(
                reply_url, json={"text": "Nhân viên đã tiếp nhận."}, headers=reply_headers
            ).status_code
            == 204
        )
        assert (
            owner_a.post(
                reply_url, json={"text": "Nhân viên đã tiếp nhận."}, headers=reply_headers
            ).status_code
            == 204
        )
        transcript = owner_a.get(
            f"/api/v1/widget/conversations/{conversation_id}/messages",
            headers={"origin": ORIGIN, "authorization": f"Bearer {token}"},
        )
        assert transcript.status_code == 200
        assert transcript.json()["waiting_human"] is True
        assert [item["text"] for item in transcript.json()["items"]].count(
            "Nhân viên đã tiếp nhận."
        ) == 1

        cross_workspace = owner_b.patch(
            state_url,
            json={"state_version": 1, "handling_mode": "human"},
            headers=csrf_headers(owner_b),
        )
        assert cross_workspace.status_code == 404
        for suffix, payload, extra_headers in (
            ("read", None, {}),
            ("notes", {"body": "Không thuộc workspace"}, {}),
            ("tags", {"name": "Sai workspace"}, {}),
            (
                "replies",
                {"text": "Không được gửi"},
                {"idempotency-key": "cross-workspace-reply"},
            ),
        ):
            denied = owner_b.post(
                f"{conversation_url}/{suffix}",
                json=payload,
                headers={**csrf_headers(owner_b), **extra_headers},
            )
            assert denied.status_code == 404
        assert shop_b["workspace_id"] != shop_a["workspace_id"]


def test_playground_and_widget_share_the_monthly_generation_quota(
    app_factory: AppFactory,
) -> None:
    runtime = FakeRuntime()
    app = app_factory(runtime, limit=1)
    with TestClient(app) as owner:
        shop = publish_agent(owner, "owner@example.com", "shop")
        playground = owner.post(
            f"{shop['base']}/playground/messages:stream",
            json={"message": "Thử chatbot", "history": []},
            headers=csrf_headers(owner),
        )
        assert playground.status_code == 200
        token, conversation = visitor(owner, shop["agent_id"])
        denied = send(owner, token, conversation, "widget-after-playground")
        assert denied.status_code == 429
        assert runtime.calls == 1
