import asyncio
import io
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
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
from agent_hub_api.agents.tool_schemas import CatalogToolImageReference
from agent_hub_api.catalog.models import Product, ProductImage
from agent_hub_api.core.config import Settings
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.main import create_app
from agent_hub_api.models import Base
from agent_hub_api.widget.image_storage import VisitorImageStorageError
from agent_hub_api.widget.vision import VisionObservation, VisionResult

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"
ABUSE_KEY = "widget-test-abuse-key-with-at-least-32-bytes"


class FakePublishedRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[AgentExecutionContext, str, tuple[AgentConversationTurn, ...]]] = []
        self.response = grounded_response()

    async def run(
        self,
        *,
        workspace_id: UUID,
        public_agent_id: UUID,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse:
        del workspace_id, public_agent_id, question, history
        raise AssertionError("Public widget must execute from its pinned revision context")

    async def run_with_context(
        self,
        context: AgentExecutionContext,
        *,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse:
        self.calls.append((context, question, history))
        return self.response


class FakeVisitorImageStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None:
        if object_key in self.objects:
            raise VisitorImageStorageError("duplicate test object")
        self.objects[object_key] = (content, content_type)

    async def download(self, *, object_key: str, max_bytes: int) -> bytes:
        content = self.objects[object_key][0]
        if len(content) > max_bytes:
            raise VisitorImageStorageError("oversized test object")
        return content

    async def delete(self, *, object_key: str) -> None:
        self.objects.pop(object_key, None)


class FakeVisionGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, str]] = []

    async def analyze(self, *, content: bytes, content_type: str) -> VisionResult:
        self.calls.append((content, content_type))
        return VisionResult(
            observation=VisionObservation(
                category="áo sơ mi",
                colors=["xanh"],
                materials=["linen"],
                patterns=[],
                style_cues=["tối giản"],
                summary="Áo sơ mi linen màu xanh phong cách tối giản.",
            ),
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
        )


class FakeCatalogStorage:
    def __init__(self) -> None:
        self.signed_keys: list[str] = []

    async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None:
        del object_key, content, content_type

    async def delete(self, *, object_key: str) -> None:
        del object_key

    async def create_signed_url(self, *, object_key: str, expires_in: int) -> str:
        self.signed_keys.append(object_key)
        return f"https://storage.example/signed/catalog.jpg?expires={expires_in}"


class AppFactory(Protocol):
    def __call__(
        self,
        runtime: FakePublishedRuntime,
        *,
        image_storage: FakeVisitorImageStorage | None = None,
        vision_gateway: FakeVisionGateway | None = None,
        catalog_storage: FakeCatalogStorage | None = None,
        **settings_overrides: object,
    ) -> FastAPI: ...


def grounded_response() -> GroundedAgentResponse:
    return GroundedAgentResponse.model_validate(
        {
            "text": "Mình tìm thấy sản phẩm phù hợp trong catalog.",
            "product_cards": [
                {
                    "product_id": 7,
                    "sku": "LINEN-7",
                    "name": "Áo linen",
                    "product_url": f"{ORIGIN}/products/linen",
                    "currency": "VND",
                    "price": {
                        "kind": "range",
                        "minimum": "250000.00",
                        "maximum": "290000.00",
                    },
                    "availability": {
                        "total_locations": 2,
                        "in_stock_locations": 1,
                        "out_of_stock_locations": 0,
                        "unknown_locations": 1,
                    },
                    "options": {"Màu": ["Xanh", "Trắng"]},
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
                    "source_id": "internal-source",
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
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    resources: list[AsyncEngine] = []

    def build(
        runtime: FakePublishedRuntime,
        *,
        image_storage: FakeVisitorImageStorage | None = None,
        vision_gateway: FakeVisionGateway | None = None,
        catalog_storage: FakeCatalogStorage | None = None,
        **settings_overrides: object,
    ) -> FastAPI:
        database_path = tmp_path / f"widget-public-{len(resources)}.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        resources.append(engine)
        values: dict[str, object] = {
            "app_env": "test",
            "jwt_signing_key": "test-signing-key-with-at-least-32-bytes",
            "widget_public_base_url": "http://127.0.0.1:4173",
            "widget_abuse_hash_key": ABUSE_KEY,
        }
        values.update(settings_overrides)
        return create_app(
            settings=Settings.model_validate(values),
            session_factory=async_sessionmaker(engine, expire_on_commit=False),
            agent_runtime_factory=lambda _: runtime,
            widget_image_storage=image_storage,
            vision_gateway=vision_gateway,
            catalog_storage=catalog_storage,
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


def publish_agent(client: TestClient, email: str = "owner@example.com") -> dict[str, Any]:
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert registration.status_code == 201
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": email.split("@")[0], "display_name": "Shop"},
        headers=csrf_headers(client),
    )
    assert workspace.status_code == 201
    agent = client.post(
        f"/api/v1/workspaces/{workspace.json()['id']}/agents",
        json={"name": "Trợ lý", "safe_instructions": "revision-one"},
        headers=csrf_headers(client),
    )
    assert agent.status_code == 201
    base = f"/api/v1/workspaces/{workspace.json()['id']}/agents/{agent.json()['public_id']}"
    configured = client.put(
        f"{base}/widget",
        json={
            "display_name": "Tư vấn sản phẩm",
            "greeting": "Xin chào từ website",
            "brand_color": "#0F8F87",
            "launcher_position": "right",
            "allowed_origins": [ORIGIN],
        },
        headers=csrf_headers(client),
    )
    assert configured.status_code == 200, configured.text
    published = client.post(f"{base}/publish", headers=csrf_headers(client))
    assert published.status_code == 200, published.text
    return {
        "workspace_id": workspace.json()["id"],
        "public_agent_id": agent.json()["public_id"],
        "base": base,
    }


def visitor_session(client: TestClient, public_agent_id: str) -> tuple[str, dict[str, Any]]:
    response = client.post(
        f"/api/v1/widget/{public_agent_id}/sessions",
        headers={"origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    payload = cast(dict[str, Any], response.json())
    return cast(str, payload["access_token"]), payload


def visitor_headers(token: str, **extra: str) -> dict[str, str]:
    return {"origin": ORIGIN, "authorization": f"Bearer {token}", **extra}


def jpeg_with_exif() -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (24, 18), color=(24, 120, 160))
    exif = image.getexif()
    exif[270] = "private test metadata"
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def add_managed_product_image(app: FastAPI, workspace_id: str) -> tuple[int, str]:
    session_factory = cast(async_sessionmaker[AsyncSession], app.state.session_factory)

    async def create() -> tuple[int, str]:
        async with session_factory() as session, session.begin():
            product = Product(
                workspace_id=UUID(workspace_id),
                product_sku="IMAGE-PRODUCT",
                name="Sản phẩm có ảnh",
                currency="VND",
                inventory_policy="unknown",
                attributes_json={},
                status="active",
            )
            session.add(product)
            await session.flush()
            object_key = f"workspaces/{workspace_id}/catalog/{product.id}/private.jpg"
            image = ProductImage(
                workspace_id=UUID(workspace_id),
                product_id=product.id,
                object_key=object_key,
                original_filename="private.jpg",
                content_type="image/jpeg",
                byte_size=128,
                width=24,
                height=18,
                sha256="a" * 64,
                alt_text="Áo linen xanh",
                sort_order=0,
                status="active",
            )
            session.add(image)
            await session.flush()
            return image.id, object_key

    return asyncio.run(create())


def test_public_widget_stream_is_scoped_redacted_and_idempotent(
    app_factory: AppFactory,
) -> None:
    runtime = FakePublishedRuntime()
    app = app_factory(runtime)
    with TestClient(app) as client:
        published = publish_agent(client)
        token, session_payload = visitor_session(client, published["public_agent_id"])
        assert session_payload["config"]["display_name"] == "Tư vấn sản phẩm"
        assert session_payload["config"]["capabilities"] == {"image_input": False}

        conversation = client.post(
            "/api/v1/widget/conversations",
            headers=visitor_headers(token),
        )
        assert conversation.status_code == 201, conversation.text
        conversation_id = conversation.json()["public_id"]
        headers = visitor_headers(token, **{"idempotency-key": "request-key-0001"})
        streamed = client.post(
            f"/api/v1/widget/conversations/{conversation_id}/messages",
            json={"message": "Còn áo linen màu xanh không?"},
            headers=headers,
        )
        assert streamed.status_code == 200, streamed.text
        assert streamed.headers["access-control-allow-origin"] == ORIGIN
        assert streamed.text.index("event: message.start") < streamed.text.index(
            "event: message.delta"
        )
        assert streamed.text.index("event: message.delta") < streamed.text.index(
            "event: product.cards"
        )
        assert "product_id" not in streamed.text
        assert "variant_id" not in streamed.text
        assert "knowledge_base_id" not in streamed.text
        assert "document_id" not in streamed.text
        assert "internal-source" not in streamed.text
        assert f'"product_url":"{ORIGIN}/products/linen"' in streamed.text
        assert len(runtime.calls) == 1
        assert runtime.calls[0][0].safe_instructions == "revision-one"
        assert runtime.calls[0][1] == "Còn áo linen màu xanh không?"

        replay = client.post(
            f"/api/v1/widget/conversations/{conversation_id}/messages",
            json={"message": "Còn áo linen màu xanh không?"},
            headers=headers,
        )
        assert replay.status_code == 200
        assert "event: message.completed" in replay.text
        assert len(runtime.calls) == 1

        transcript = client.get(
            f"/api/v1/widget/conversations/{conversation_id}/messages",
            headers=visitor_headers(token),
        )
        assert transcript.status_code == 200
        assert [item["role"] for item in transcript.json()["items"]] == [
            "user",
            "assistant",
        ]
        assert "product_id" not in transcript.text


def test_public_widget_rejects_cross_origin_and_cross_session_access(
    app_factory: AppFactory,
) -> None:
    app = app_factory(FakePublishedRuntime())
    with TestClient(app) as client:
        published = publish_agent(client)
        token_a, _ = visitor_session(client, published["public_agent_id"])
        token_b, _ = visitor_session(client, published["public_agent_id"])
        conversation_a = client.post(
            "/api/v1/widget/conversations", headers=visitor_headers(token_a)
        )
        assert conversation_a.status_code == 201
        conversation_id = conversation_a.json()["public_id"]

        cross_session = client.get(
            f"/api/v1/widget/conversations/{conversation_id}/messages",
            headers=visitor_headers(token_b),
        )
        assert cross_session.status_code == 404

        cross_origin = client.get(
            f"/api/v1/widget/conversations/{conversation_id}/messages",
            headers={
                "origin": "https://evil.example",
                "authorization": f"Bearer {token_a}",
            },
        )
        assert cross_origin.status_code == 401
        assert cross_origin.headers["access-control-allow-origin"] == "https://evil.example"

        unknown_origin = client.post(
            f"/api/v1/widget/{published['public_agent_id']}/sessions",
            headers={"origin": "https://evil.example"},
        )
        assert unknown_origin.status_code == 404


def test_widget_session_pins_revision_and_rate_limits_before_generation(
    app_factory: AppFactory,
) -> None:
    runtime = FakePublishedRuntime()
    app = app_factory(runtime, widget_messages_per_session_hour=1)
    with TestClient(app) as client:
        published = publish_agent(client)
        old_token, _ = visitor_session(client, published["public_agent_id"])
        old_conversation = client.post(
            "/api/v1/widget/conversations", headers=visitor_headers(old_token)
        ).json()["public_id"]

        changed = client.patch(
            published["base"],
            json={"safe_instructions": "revision-two"},
            headers=csrf_headers(client),
        )
        assert changed.status_code == 200
        republished = client.post(f"{published['base']}/publish", headers=csrf_headers(client))
        assert republished.status_code == 200
        new_token, _ = visitor_session(client, published["public_agent_id"])
        new_conversation = client.post(
            "/api/v1/widget/conversations", headers=visitor_headers(new_token)
        ).json()["public_id"]

        first = client.post(
            f"/api/v1/widget/conversations/{old_conversation}/messages",
            json={"message": "Phiên cũ"},
            headers=visitor_headers(old_token, **{"idempotency-key": "old-turn-0001"}),
        )
        second = client.post(
            f"/api/v1/widget/conversations/{new_conversation}/messages",
            json={"message": "Phiên mới"},
            headers=visitor_headers(new_token, **{"idempotency-key": "new-turn-0001"}),
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert [call[0].safe_instructions for call in runtime.calls] == [
            "revision-one",
            "revision-two",
        ]

        limited = client.post(
            f"/api/v1/widget/conversations/{old_conversation}/messages",
            json={"message": "Vượt giới hạn"},
            headers=visitor_headers(old_token, **{"idempotency-key": "old-turn-0002"}),
        )
        assert limited.status_code == 429
        assert len(runtime.calls) == 2


def test_widget_image_is_sanitized_scoped_single_use_and_added_as_untrusted_cues(
    app_factory: AppFactory,
) -> None:
    runtime = FakePublishedRuntime()
    storage = FakeVisitorImageStorage()
    vision = FakeVisionGateway()
    app = app_factory(
        runtime,
        image_storage=storage,
        vision_gateway=vision,
        vision_model="verified-vision-test-model",
    )
    with TestClient(app) as client:
        published = publish_agent(client)
        token_a, session_payload = visitor_session(client, published["public_agent_id"])
        token_b, _ = visitor_session(client, published["public_agent_id"])
        assert session_payload["config"]["capabilities"] == {"image_input": True}
        conversation_a = client.post(
            "/api/v1/widget/conversations", headers=visitor_headers(token_a)
        ).json()["public_id"]
        conversation_b = client.post(
            "/api/v1/widget/conversations", headers=visitor_headers(token_b)
        ).json()["public_id"]

        uploaded = client.post(
            "/api/v1/widget/uploads/images",
            files={"file": ("look.jpg", jpeg_with_exif(), "image/jpeg")},
            headers=visitor_headers(token_a),
        )
        assert uploaded.status_code == 201, uploaded.text
        attachment_id = uploaded.json()["attachment_id"]
        assert len(storage.objects) == 1
        stored_content = next(iter(storage.objects.values()))[0]
        with Image.open(io.BytesIO(stored_content)) as stored_image:
            assert len(stored_image.getexif()) == 0

        denied = client.post(
            f"/api/v1/widget/conversations/{conversation_b}/messages",
            json={"message": "Tìm mẫu tương tự", "attachment_id": attachment_id},
            headers=visitor_headers(token_b, **{"idempotency-key": "image-wrong-session"}),
        )
        assert denied.status_code == 404
        assert len(runtime.calls) == 0
        assert len(vision.calls) == 0

        response = client.post(
            f"/api/v1/widget/conversations/{conversation_a}/messages",
            json={"message": "Tìm mẫu tương tự", "attachment_id": attachment_id},
            headers=visitor_headers(token_a, **{"idempotency-key": "image-right-session"}),
        )
        assert response.status_code == 200, response.text
        assert len(vision.calls) == 1
        assert len(runtime.calls) == 1
        runtime_question = runtime.calls[0][1]
        assert "<image_cues>" in runtime_question
        assert "áo sơ mi" in runtime_question
        assert "dữ liệu không tin cậy" in runtime_question
        assert next(iter(storage.objects)) not in runtime_question
        assert '"total_tokens":200' in response.text
        usage = client.get(f"/api/v1/workspaces/{published['workspace_id']}/usage")
        assert usage.status_code == 200
        assert usage.json()["generation_model_calls"] == 2
        assert usage.json()["vision_model_calls"] == 1
        assert usage.json()["total_tokens"] == 200

        reused = client.post(
            f"/api/v1/widget/conversations/{conversation_a}/messages",
            json={"message": "Dùng lại ảnh", "attachment_id": attachment_id},
            headers=visitor_headers(token_a, **{"idempotency-key": "image-reuse-handle"}),
        )
        assert reused.status_code == 404
        assert len(runtime.calls) == 1

        deleted = client.delete(
            f"/api/v1/widget/conversations/{conversation_a}",
            headers=visitor_headers(token_a),
        )
        assert deleted.status_code == 204
        assert storage.objects == {}


def test_widget_image_rejects_invalid_content_mime_and_quota(
    app_factory: AppFactory,
) -> None:
    storage = FakeVisitorImageStorage()
    vision = FakeVisionGateway()
    app = app_factory(
        FakePublishedRuntime(),
        image_storage=storage,
        vision_gateway=vision,
        vision_model="verified-vision-test-model",
        widget_image_session_max_uploads=1,
    )
    with TestClient(app) as client:
        published = publish_agent(client)
        token, _ = visitor_session(client, published["public_agent_id"])

        oversized = client.post(
            "/api/v1/widget/uploads/images",
            files={
                "file": (
                    "large.jpg",
                    b"x" * (5 * 1024 * 1024 + 1),
                    "image/jpeg",
                )
            },
            headers=visitor_headers(token),
        )
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "IMAGE_TOO_LARGE"

        malformed = client.post(
            "/api/v1/widget/uploads/images",
            files={"file": ("bad.png", b"not-an-image", "image/png")},
            headers=visitor_headers(token),
        )
        assert malformed.status_code == 415
        assert malformed.json()["error"]["code"] == "INVALID_IMAGE"

        mismatch = client.post(
            "/api/v1/widget/uploads/images",
            files={"file": ("look.png", jpeg_with_exif(), "image/png")},
            headers=visitor_headers(token),
        )
        assert mismatch.status_code == 415
        assert mismatch.json()["error"]["code"] == "IMAGE_TYPE_MISMATCH"

        accepted = client.post(
            "/api/v1/widget/uploads/images",
            files={"file": ("look.jpg", jpeg_with_exif(), "image/jpeg")},
            headers=visitor_headers(token),
        )
        assert accepted.status_code == 201
        limited = client.post(
            "/api/v1/widget/uploads/images",
            files={"file": ("second.jpg", jpeg_with_exif(), "image/jpeg")},
            headers=visitor_headers(token),
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "IMAGE_QUOTA_EXCEEDED"


def test_widget_image_capability_and_endpoint_stay_disabled_without_vision_model(
    app_factory: AppFactory,
) -> None:
    app = app_factory(FakePublishedRuntime())
    with TestClient(app) as client:
        published = publish_agent(client)
        token, session_payload = visitor_session(client, published["public_agent_id"])
        assert session_payload["config"]["capabilities"] == {"image_input": False}
        disabled = client.post(
            "/api/v1/widget/uploads/images",
            files={"file": ("look.jpg", jpeg_with_exif(), "image/jpeg")},
            headers=visitor_headers(token),
        )
        assert disabled.status_code == 503
        assert disabled.json()["error"]["code"] == "IMAGE_INPUT_DISABLED"


def test_managed_product_image_uses_scoped_public_grant_without_internal_ids(
    app_factory: AppFactory,
) -> None:
    runtime = FakePublishedRuntime()
    catalog_storage = FakeCatalogStorage()
    app = app_factory(runtime, catalog_storage=catalog_storage)
    with TestClient(app) as client:
        published = publish_agent(client)
        image_id, object_key = add_managed_product_image(app, published["workspace_id"])
        runtime.response.product_cards[0].images = [
            CatalogToolImageReference(
                image_id=image_id,
                variant_id=None,
                kind="managed",
                alt_text="Áo linen xanh",
                sort_order=0,
            )
        ]
        token_a, _ = visitor_session(client, published["public_agent_id"])
        token_b, _ = visitor_session(client, published["public_agent_id"])
        conversation = client.post(
            "/api/v1/widget/conversations", headers=visitor_headers(token_a)
        ).json()["public_id"]
        response = client.post(
            f"/api/v1/widget/conversations/{conversation}/messages",
            json={"message": "Cho mình xem ảnh"},
            headers=visitor_headers(token_a, **{"idempotency-key": "catalog-image-grant"}),
        )
        assert response.status_code == 200, response.text
        assert "image_id" not in response.text
        assert "object_key" not in response.text
        match = re.search(r'"url":"(/api/v1/widget/product-images/[0-9a-f-]+)"', response.text)
        assert match is not None
        image_path = match.group(1)

        denied = client.get(
            image_path,
            headers=visitor_headers(token_b),
            follow_redirects=False,
        )
        assert denied.status_code == 404
        allowed = client.get(
            image_path,
            headers=visitor_headers(token_a),
            follow_redirects=False,
        )
        assert allowed.status_code == 307
        assert allowed.headers["location"].startswith("https://storage.example/signed/")
        assert catalog_storage.signed_keys == [object_key]
