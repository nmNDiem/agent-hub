import asyncio
from collections.abc import Iterator
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

from agent_hub_api.agents.runtime import (
    AgentConversationTurn,
    AgentExecutionContext,
    GroundedAgentResponse,
)
from agent_hub_api.core.config import Settings
from agent_hub_api.identity.models import User
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.leads.models import Lead
from agent_hub_api.leads.schemas import CONTACT_CONSENT_VERSION
from agent_hub_api.main import create_app
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import WorkspaceMember

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"
ABUSE_KEY = "widget-test-abuse-key-with-at-least-32-bytes"


class FakeRuntime:
    async def run(
        self,
        *,
        workspace_id: UUID,
        public_agent_id: UUID,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse:
        del workspace_id, public_agent_id
        return await self._response(question, history)

    async def run_with_context(
        self,
        context: AgentExecutionContext,
        *,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse:
        del context
        return await self._response(question, history)

    async def _response(
        self, question: str, history: tuple[AgentConversationTurn, ...]
    ) -> GroundedAgentResponse:
        del question, history
        return GroundedAgentResponse.model_validate(
            {
                "text": "Mình vẫn sẵn sàng hỗ trợ mà không cần thông tin liên hệ.",
                "product_cards": [],
                "sources": [],
                "usage": {
                    "model_calls": 1,
                    "tool_calls": 0,
                    "input_tokens": 5,
                    "output_tokens": 8,
                    "total_tokens": 13,
                },
            }
        )


class AppFactory(Protocol):
    def __call__(self) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]: ...


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    engines: list[AsyncEngine] = []

    def build() -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / f'leads-{len(engines)}.db'}"
        )

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        engines.append(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app = create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
                widget_public_base_url="http://127.0.0.1:4173",
                widget_abuse_hash_key=ABUSE_KEY,
            ),
            session_factory=session_factory,
            agent_runtime_factory=lambda _: FakeRuntime(),
        )
        return app, session_factory

    yield build

    async def dispose() -> None:
        for engine in engines:
            await engine.dispose()

    asyncio.run(dispose())


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"x-csrf-token": token, "origin": ORIGIN}


def create_published_agent(
    client: TestClient, email: str, slug: str
) -> dict[str, str]:
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert registration.status_code == 201
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": slug, "display_name": slug},
        headers=csrf_headers(client),
    )
    agent = client.post(
        f"/api/v1/workspaces/{workspace.json()['id']}/agents",
        json={"name": "Trợ lý", "safe_instructions": "Chỉ dùng dữ liệu thật"},
        headers=csrf_headers(client),
    )
    base = f"/api/v1/workspaces/{workspace.json()['id']}/agents/{agent.json()['public_id']}"
    configured = client.put(
        f"{base}/widget",
        json={
            "display_name": "Trợ lý cửa hàng",
            "greeting": "Xin chào",
            "brand_color": "#0F8F87",
            "launcher_position": "right",
            "allowed_origins": [ORIGIN],
            "handoff_url": "https://shop.example/contact",
            "handoff_label": "Liên hệ trực tiếp",
        },
        headers=csrf_headers(client),
    )
    assert configured.status_code == 200, configured.text
    assert client.post(f"{base}/publish", headers=csrf_headers(client)).status_code == 200
    return {
        "workspace_id": workspace.json()["id"],
        "public_agent_id": agent.json()["public_id"],
        "base": base,
    }


def create_visitor(client: TestClient, public_agent_id: str) -> tuple[str, str, dict[str, Any]]:
    session = client.post(
        f"/api/v1/widget/{public_agent_id}/sessions", headers={"origin": ORIGIN}
    )
    assert session.status_code == 200, session.text
    token = cast(str, session.json()["access_token"])
    conversation = client.post(
        "/api/v1/widget/conversations",
        headers={"origin": ORIGIN, "authorization": f"Bearer {token}"},
    )
    assert conversation.status_code == 201
    return token, conversation.json()["public_id"], cast(dict[str, Any], session.json())


def visitor_headers(token: str, key: str) -> dict[str, str]:
    return {
        "origin": ORIGIN,
        "authorization": f"Bearer {token}",
        "idempotency-key": key,
    }


def lead_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "=Potential Customer",
        "email": "Customer@Example.com",
        "phone": None,
        "consent_given": True,
        "consent_text_version": CONTACT_CONSENT_VERSION,
    }
    payload.update(overrides)
    return payload


def test_consented_lead_is_scoped_validated_and_idempotent(
    app_factory: AppFactory,
) -> None:
    app, session_factory = app_factory()
    with TestClient(app) as owner:
        published = create_published_agent(owner, "owner@example.com", "shop")
        unsafe_handoff = owner.put(
            f"{published['base']}/widget",
            json={
                "display_name": "Trợ lý cửa hàng",
                "greeting": "Xin chào",
                "brand_color": "#0F8F87",
                "launcher_position": "right",
                "allowed_origins": [ORIGIN],
                "handoff_url": "javascript:alert(1)",
                "handoff_label": "Không an toàn",
            },
            headers=csrf_headers(owner),
        )
        assert unsafe_handoff.status_code == 422
        token_a, conversation_a, public_config = create_visitor(
            owner, published["public_agent_id"]
        )
        token_b, _, _ = create_visitor(owner, published["public_agent_id"])
        assert public_config["config"]["contact"]["handoff_url"] == (
            "https://shop.example/contact"
        )
        assert public_config["config"]["contact"]["consent_text_version"] == (
            CONTACT_CONSENT_VERSION
        )

        missing_contact = owner.post(
            f"/api/v1/widget/conversations/{conversation_a}/leads",
            json=lead_payload(email=None, phone=None),
            headers=visitor_headers(token_a, "lead-missing-contact"),
        )
        assert missing_contact.status_code == 422
        missing_consent = owner.post(
            f"/api/v1/widget/conversations/{conversation_a}/leads",
            json=lead_payload(consent_given=False),
            headers=visitor_headers(token_a, "lead-missing-consent"),
        )
        assert missing_consent.status_code == 422
        cross_session = owner.post(
            f"/api/v1/widget/conversations/{conversation_a}/leads",
            json=lead_payload(),
            headers=visitor_headers(token_b, "lead-cross-session"),
        )
        assert cross_session.status_code == 404

        created = owner.post(
            f"/api/v1/widget/conversations/{conversation_a}/leads",
            json=lead_payload(),
            headers=visitor_headers(token_a, "lead-create-0001"),
        )
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "received"
        assert "email" not in created.json()
        replay = owner.post(
            f"/api/v1/widget/conversations/{conversation_a}/leads",
            json=lead_payload(),
            headers=visitor_headers(token_a, "lead-create-0001"),
        )
        assert replay.status_code == 201
        conflict = owner.post(
            f"/api/v1/widget/conversations/{conversation_a}/leads",
            json=lead_payload(email="other@example.com"),
            headers=visitor_headers(token_a, "lead-create-0001"),
        )
        assert conflict.status_code == 409

        chat = owner.post(
            f"/api/v1/widget/conversations/{conversation_a}/messages",
            json={"message": "Tôi chưa muốn cung cấp thêm thông tin."},
            headers=visitor_headers(token_a, "message-after-lead"),
        )
        assert chat.status_code == 200
        assert "event: message.completed" in chat.text

    async def count_leads() -> int:
        async with session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(Lead))
            return int(count or 0)

    assert asyncio.run(count_leads()) == 1


def test_owner_admin_lead_workflow_enforces_role_csrf_workspace_and_safe_csv(
    app_factory: AppFactory,
) -> None:
    app, session_factory = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        shop_a = create_published_agent(owner_a, "owner-a@example.com", "shop-a")
        shop_b = create_published_agent(owner_b, "owner-b@example.com", "shop-b")
        token, conversation, _ = create_visitor(owner_a, shop_a["public_agent_id"])
        token_b, _, _ = create_visitor(owner_b, shop_b["public_agent_id"])
        public_cross_workspace = owner_b.post(
            f"/api/v1/widget/conversations/{conversation}/leads",
            json=lead_payload(),
            headers=visitor_headers(token_b, "lead-cross-workspace"),
        )
        assert public_cross_workspace.status_code == 404
        assert owner_a.post(
            f"/api/v1/widget/conversations/{conversation}/leads",
            json=lead_payload(),
            headers=visitor_headers(token, "lead-admin-flow"),
        ).status_code == 201
        second_token, second_conversation, _ = create_visitor(
            owner_a, shop_a["public_agent_id"]
        )
        assert owner_a.post(
            f"/api/v1/widget/conversations/{second_conversation}/leads",
            json=lead_payload(name="Khách thứ hai", email=None, phone="090 123 4567"),
            headers=visitor_headers(second_token, "lead-admin-flow-2"),
        ).status_code == 201

        listed = owner_a.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/leads?limit=1"
        )
        assert listed.status_code == 200
        assert listed.headers["cache-control"] == "no-store"
        item = listed.json()["items"][0]
        assert listed.json()["next_cursor"] is not None
        second_page = owner_a.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/leads",
            params={"limit": 1, "cursor": listed.json()["next_cursor"]},
        )
        assert second_page.status_code == 200
        assert {
            item["conversation_public_id"],
            second_page.json()["items"][0]["conversation_public_id"],
        } == {conversation, second_conversation}

        no_csrf = owner_a.patch(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/leads/{item['id']}",
            json={"followup_status": "contacted"},
        )
        assert no_csrf.status_code == 403
        updated = owner_a.patch(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/leads/{item['id']}",
            json={"followup_status": "contacted"},
            headers=csrf_headers(owner_a),
        )
        assert updated.status_code == 200
        assert updated.json()["followup_status"] == "contacted"

        exported = owner_a.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/leads/export.csv"
        )
        assert exported.status_code == 200
        assert exported.headers["cache-control"] == "no-store"
        assert "text/csv" in exported.headers["content-type"]
        assert "'=Potential Customer" in exported.content.decode("utf-8-sig")

        assert owner_b.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/leads"
        ).status_code == 404
        assert owner_a.get(
            f"/api/v1/workspaces/{shop_b['workspace_id']}/leads"
        ).status_code == 404

        async def set_member_role(role: str) -> None:
            async with session_factory() as session, session.begin():
                member = await session.scalar(
                    select(User).where(User.normalized_email == "owner-b@example.com")
                )
                assert member is not None
                membership = await session.scalar(
                    select(WorkspaceMember).where(
                        WorkspaceMember.workspace_id == UUID(shop_a["workspace_id"]),
                        WorkspaceMember.user_id == member.id,
                    )
                )
                if membership is None:
                    session.add(
                        WorkspaceMember(
                            workspace_id=UUID(shop_a["workspace_id"]),
                            user_id=member.id,
                            role=role,
                        )
                    )
                else:
                    membership.role = role

        asyncio.run(set_member_role("admin"))
        assert owner_b.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/leads"
        ).status_code == 200
        asyncio.run(set_member_role("member"))
        assert owner_b.get(
            f"/api/v1/workspaces/{shop_a['workspace_id']}/leads"
        ).status_code == 403
