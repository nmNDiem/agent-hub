import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.agents.playground import AgentRuntimeFactory
from agent_hub_api.agents.runtime import (
    AgentConversationTurn,
    AgentRuntimeError,
    GroundedAgentResponse,
)
from agent_hub_api.core.config import Settings
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.main import create_app
from agent_hub_api.models import Base

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"


class FakeRuntime:
    def __init__(self, response: GroundedAgentResponse) -> None:
        self.response = response
        self.calls: list[tuple[UUID, UUID, str, tuple[AgentConversationTurn, ...]]] = []
        self.error: AgentRuntimeError | None = None

    async def run(
        self,
        *,
        workspace_id: UUID,
        public_agent_id: UUID,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse:
        self.calls.append((workspace_id, public_agent_id, question, history))
        if self.error is not None:
            raise self.error
        return self.response


def grounded_response() -> GroundedAgentResponse:
    return GroundedAgentResponse.model_validate(
        {
            "text": "Mình tìm thấy sản phẩm phù hợp trong catalog.",
            "product_cards": [
                {
                    "product_id": 7,
                    "sku": "LINEN-7",
                    "name": "Áo linen",
                    "product_url": "https://shop.example/products/linen",
                    "currency": "VND",
                    "price": {"kind": "range", "minimum": "250000.00", "maximum": "290000.00"},
                    "availability": {
                        "total_locations": 2,
                        "in_stock_locations": 1,
                        "out_of_stock_locations": 0,
                        "unknown_locations": 1,
                    },
                    "options": {"Màu": ["Xanh", "Trắng"], "Chất liệu": ["Linen"]},
                    "attributes": {"fit": "regular"},
                    "variants": [
                        {
                            "variant_id": 11,
                            "sku": "LINEN-BLUE",
                            "name": "Xanh",
                            "options": {"Màu": "Xanh"},
                            "attributes": {},
                            "inventory_state": "in_stock",
                        }
                    ],
                    "images": [],
                }
            ],
            "sources": [
                {
                    "source_id": "source_1",
                    "knowledge_base_id": 3,
                    "document_id": 9,
                    "document_title": "Chính sách cửa hàng",
                    "chunk_id": 15,
                    "source_locator": "Trang 1",
                }
            ],
            "usage": {
                "model_calls": 2,
                "tool_calls": 1,
                "input_tokens": 100,
                "output_tokens": 30,
                "total_tokens": 130,
            },
        }
    )


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[Any]:
    resources: list[AsyncEngine] = []

    def build(runtime_factory: AgentRuntimeFactory | None) -> FastAPI:
        database_path = tmp_path / f"playground-{len(resources)}.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        resources.append(engine)
        return create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
            ),
            session_factory=async_sessionmaker(engine, expire_on_commit=False),
            agent_runtime_factory=runtime_factory,
        )

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
) -> tuple[dict[str, Any], dict[str, Any]]:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert registered.status_code == 201
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": slug, "display_name": slug},
        headers=csrf_headers(client),
    )
    assert workspace.status_code == 201
    workspace_payload = cast(dict[str, Any], workspace.json())
    agent = client.post(
        f"/api/v1/workspaces/{workspace_payload['id']}/agents",
        json={"name": "Tư vấn viên"},
        headers=csrf_headers(client),
    )
    assert agent.status_code == 201
    return workspace_payload, cast(dict[str, Any], agent.json())


def test_playground_stream_is_scoped_and_emits_validated_events(app_factory: Any) -> None:
    runtime = FakeRuntime(grounded_response())
    app = app_factory(lambda _: runtime)
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        workspace, agent = create_workspace_and_agent(owner_a, "owner-a@example.com", "shop-a")
        create_workspace_and_agent(owner_b, "owner-b@example.com", "shop-b")

        denied = owner_b.post(
            f"/api/v1/workspaces/{workspace['id']}/agents/{agent['public_id']}"
            "/playground/messages:stream",
            json={"message": "Có áo linen không?"},
            headers=csrf_headers(owner_b),
        )
        assert denied.status_code == 404

        response = owner_a.post(
            f"/api/v1/workspaces/{workspace['id']}/agents/{agent['public_id']}"
            "/playground/messages:stream",
            json={
                "message": "Còn màu nào?",
                "history": [
                    {"role": "user", "content": "Có áo linen không?"},
                    {"role": "assistant", "content": "Mình đã tìm thấy một sản phẩm."},
                ],
            },
            headers=csrf_headers(owner_a),
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
        body = response.text
        assert body.index("event: message.start") < body.index("event: message.delta")
        assert body.index("event: message.delta") < body.index("event: product.cards")
        assert body.index("event: product.cards") < body.index("event: source.refs")
        assert body.index("event: source.refs") < body.index("event: message.completed")
        assert '"Màu":["Xanh","Trắng"]' in body
        assert len(runtime.calls) == 1
        assert runtime.calls[0][2] == "Còn màu nào?"
        assert [turn.role for turn in runtime.calls[0][3]] == ["user", "assistant"]


def test_playground_reports_disabled_and_safe_runtime_errors(app_factory: Any) -> None:
    disabled_app = app_factory(None)
    with TestClient(disabled_app) as client:
        workspace, agent = create_workspace_and_agent(client, "disabled@example.com", "disabled")
        disabled = client.post(
            f"/api/v1/workspaces/{workspace['id']}/agents/{agent['public_id']}"
            "/playground/messages:stream",
            json={"message": "Xin chào"},
            headers=csrf_headers(client),
        )
        assert disabled.status_code == 503
        assert disabled.json()["error"]["code"] == "AGENT_RUNTIME_DISABLED"

    runtime = FakeRuntime(grounded_response())
    runtime.error = AgentRuntimeError(
        "GENERATION_UNAVAILABLE", "Không thể tạo câu trả lời an toàn."
    )
    error_app = app_factory(lambda _: runtime)
    with TestClient(error_app) as client:
        workspace, agent = create_workspace_and_agent(client, "error@example.com", "error")
        failed = client.post(
            f"/api/v1/workspaces/{workspace['id']}/agents/{agent['public_id']}"
            "/playground/messages:stream",
            json={"message": "Xin chào"},
            headers=csrf_headers(client),
        )
        assert failed.status_code == 200
        assert "event: message.error" in failed.text
        assert "GENERATION_UNAVAILABLE" in failed.text
        assert "sk-" not in failed.text
