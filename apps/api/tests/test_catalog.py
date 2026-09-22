import asyncio
import csv
import hashlib
import io
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agent_hub_api.catalog.models import CatalogImport, Product, ProductImage, ProductVariant
from agent_hub_api.catalog.storage import StorageError
from agent_hub_api.core.config import Settings
from agent_hub_api.identity.security import CSRF_COOKIE
from agent_hub_api.main import create_app
from agent_hub_api.models import Base

PASSWORD = "secure-password-123"
ORIGIN = "http://127.0.0.1:3000"
CSV_COLUMNS = [
    "product_sku",
    "name",
    "description",
    "category",
    "currency",
    "price",
    "product_url",
    "variant_sku",
    "variant_name",
    "color",
    "size",
    "variant_price",
    "stock_quantity",
]


class FakeCatalogStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_delete = False

    async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None:
        self.objects[object_key] = content

    async def delete(self, *, object_key: str) -> None:
        if self.fail_delete:
            raise StorageError("simulated delete failure")
        self.objects.pop(object_key, None)

    async def create_signed_url(self, *, object_key: str, expires_in: int) -> str:
        if object_key not in self.objects:
            raise StorageError("missing")
        return f"https://storage.example.test/signed/{object_key}?expires={expires_in}"


class AppFactory(Protocol):
    def __call__(
        self,
    ) -> tuple[FastAPI, async_sessionmaker[AsyncSession], FakeCatalogStorage]: ...


@pytest.fixture
def app_factory(tmp_path: Path) -> Iterator[AppFactory]:
    resources: list[AsyncEngine] = []

    def build() -> tuple[FastAPI, async_sessionmaker[AsyncSession], FakeCatalogStorage]:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / f'catalog-{len(resources)}.db'}"
        )

        async def prepare() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare())
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        storage = FakeCatalogStorage()
        app = create_app(
            settings=Settings(
                app_env="test",
                jwt_signing_key="test-signing-key-with-at-least-32-bytes",
            ),
            session_factory=session_factory,
            catalog_storage=storage,
        )
        resources.append(engine)
        return app, session_factory, storage

    yield build

    async def dispose() -> None:
        for engine in resources:
            await engine.dispose()

    asyncio.run(dispose())


def register_and_create_workspace(client: TestClient, email: str, slug: str) -> dict[str, Any]:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers={"origin": ORIGIN},
    )
    assert registered.status_code == 201, registered.text
    created = client.post(
        "/api/v1/workspaces",
        json={"display_name": slug, "slug": slug},
        headers=csrf_headers(client),
    )
    assert created.status_code == 201, created.text
    return cast(dict[str, Any], created.json())


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"x-csrf-token": token, "origin": ORIGIN}


def create_product(
    client: TestClient,
    workspace_id: str,
    *,
    sku: str | None = "PRODUCT-1",
    name: str = "Product",
    price: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/products",
        json={"product_sku": sku, "name": name, "currency": "VND", "price": price},
        headers=csrf_headers(client),
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), color=(20, 40, 80)).save(output, format="PNG")
    return output.getvalue()


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def csv_row(index: int, *, variant: bool = True) -> dict[str, str]:
    return {
        "product_sku": f"P-{index}",
        "name": f"Product {index}",
        "description": "",
        "category": "General",
        "currency": "VND",
        "price": "0" if index == 1 else "100.25",
        "product_url": "",
        "variant_sku": f"V-{index}" if variant else "",
        "variant_name": "Default" if variant else "",
        "color": "" if not variant else "Blue",
        "size": "" if not variant else "M",
        "variant_price": "0" if index == 1 and variant else "",
        "stock_quantity": "0" if index == 1 and variant else "",
    }


def test_catalog_preserves_null_and_zero_and_archived_skus_remain_reserved(
    app_factory: AppFactory,
) -> None:
    app, _, _ = app_factory()
    with TestClient(app) as client:
        workspace = register_and_create_workspace(client, "owner@example.com", "shop")
        product = create_product(client, workspace["id"], price=None)
        assert product["price"] is None
        assert product["variants"] == []
        assert product["size_guide"] is None

        variant = client.post(
            f"/api/v1/workspaces/{workspace['id']}/products/{product['id']}/variants",
            json={"variant_sku": "variant-1", "price_override": "0", "stock_quantity": 0},
            headers=csrf_headers(client),
        )
        assert variant.status_code == 201, variant.text
        assert variant.json()["price_override"] == "0.00"
        assert variant.json()["effective_price"] == "0.00"
        assert variant.json()["stock_quantity"] == 0

        inherited = client.post(
            f"/api/v1/workspaces/{workspace['id']}/products/{product['id']}/variants",
            json={"variant_sku": "variant-unknown"},
            headers=csrf_headers(client),
        )
        assert inherited.status_code == 201
        assert inherited.json()["price_override"] is None
        assert inherited.json()["effective_price"] is None
        assert inherited.json()["stock_quantity"] is None

        guide = client.put(
            f"/api/v1/workspaces/{workspace['id']}/products/{product['id']}/size-guide",
            json={"title": "Generic option guide", "content": {"options": ["A", "B"]}},
            headers=csrf_headers(client),
        )
        assert guide.status_code == 200
        assert guide.json()["content"] == {"options": ["A", "B"]}

        archived_variant = client.delete(
            f"/api/v1/workspaces/{workspace['id']}/products/{product['id']}"
            f"/variants/{variant.json()['id']}",
            headers=csrf_headers(client),
        )
        assert archived_variant.status_code == 204
        second_product = create_product(client, workspace["id"], sku="PRODUCT-2")
        duplicate_variant = client.post(
            f"/api/v1/workspaces/{workspace['id']}/products/{second_product['id']}/variants",
            json={"variant_sku": "VARIANT-1"},
            headers=csrf_headers(client),
        )
        assert duplicate_variant.status_code == 409

        archived = client.delete(
            f"/api/v1/workspaces/{workspace['id']}/products/{product['id']}",
            headers=csrf_headers(client),
        )
        assert archived.status_code == 204
        duplicate = client.post(
            f"/api/v1/workspaces/{workspace['id']}/products",
            json={"product_sku": "product-1", "name": "Replacement"},
            headers=csrf_headers(client),
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "SKU_CONFLICT"


def test_product_image_access_is_tenant_scoped_and_cleanup_is_retryable(
    app_factory: AppFactory,
) -> None:
    app, session_factory, storage = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        workspace_a = register_and_create_workspace(owner_a, "a@example.com", "shop-a")
        product = create_product(owner_a, workspace_a["id"])
        upload = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}/images",
            files={"file": ("product.png", png_bytes(), "image/png")},
            data={"alt_text": "Catalog product"},
            headers=csrf_headers(owner_a),
        )
        assert upload.status_code == 201, upload.text
        image_id = upload.json()["id"]
        signed = owner_a.get(
            f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}"
            f"/images/{image_id}/signed-url"
        )
        assert signed.status_code == 200
        assert signed.json()["url"].startswith("https://storage.example.test/signed/")

        register_and_create_workspace(owner_b, "b@example.com", "shop-b")
        assert (
            owner_b.get(
                f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}"
            ).status_code
            == 404
        )
        assert (
            owner_b.patch(
                f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}",
                json={"name": "Stolen"},
                headers=csrf_headers(owner_b),
            ).status_code
            == 404
        )
        assert (
            owner_b.post(
                f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}/variants",
                json={"variant_sku": "STOLEN"},
                headers=csrf_headers(owner_b),
            ).status_code
            == 404
        )
        assert (
            owner_b.put(
                f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}/size-guide",
                json={"title": "Stolen", "content": {"rows": []}},
                headers=csrf_headers(owner_b),
            ).status_code
            == 404
        )
        assert (
            owner_b.post(
                f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}/images",
                files={"file": ("stolen.png", png_bytes(), "image/png")},
                headers=csrf_headers(owner_b),
            ).status_code
            == 404
        )
        assert (
            owner_b.post(
                f"/api/v1/workspaces/{workspace_a['id']}/catalog/import/preview",
                files={"file": ("catalog.csv", csv_bytes([csv_row(99)]), "text/csv")},
                headers=csrf_headers(owner_b),
            ).status_code
            == 404
        )
        denied = owner_b.get(
            f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}"
            f"/images/{image_id}/signed-url"
        )
        assert denied.status_code == 404

        forged = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}/images",
            files={"file": ("forged.jpg", png_bytes(), "image/jpeg")},
            headers=csrf_headers(owner_a),
        )
        assert forged.status_code == 415
        assert forged.json()["error"]["code"] == "IMAGE_TYPE_MISMATCH"

        storage.fail_delete = True
        pending = owner_a.delete(
            f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}/images/{image_id}",
            headers=csrf_headers(owner_a),
        )
        assert pending.status_code == 200
        assert pending.json()["status"] == "cleanup_pending"

        async def image_status() -> tuple[str, int]:
            async with session_factory() as session:
                image = await session.get(ProductImage, image_id)
                assert image is not None
                return image.status, image.cleanup_attempts

        assert asyncio.run(image_status()) == ("cleanup_pending", 1)
        storage.fail_delete = False
        cleaned = owner_a.post(
            f"/api/v1/workspaces/{workspace_a['id']}/products/{product['id']}"
            f"/images/{image_id}/cleanup",
            headers=csrf_headers(owner_a),
        )
        assert cleaned.status_code == 200
        assert cleaned.json()["status"] == "deleted"


def test_csv_import_groups_products_is_idempotent_and_revalidates_preview(
    app_factory: AppFactory,
) -> None:
    app, session_factory, _ = app_factory()
    rows = [csv_row(index) for index in range(1, 22)]
    rows.append({**csv_row(1), "variant_sku": "V-1-B", "size": "L"})
    content = csv_bytes(rows)
    with TestClient(app) as client:
        workspace = register_and_create_workspace(client, "owner@example.com", "shop")
        preview = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import/preview",
            files={"file": ("catalog.csv", content, "text/csv")},
            headers=csrf_headers(client),
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["product_count"] == 21
        assert preview.json()["variant_count"] == 22
        assert preview.json()["errors"] == []

        commit_headers = {**csrf_headers(client), "Idempotency-Key": "catalog-seed-1"}
        committed = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import",
            files={"file": ("catalog.csv", content, "text/csv")},
            data={"preview_sha256": preview.json()["payload_sha256"]},
            headers=commit_headers,
        )
        assert committed.status_code == 200, committed.text
        assert committed.json()["product_count"] == 21
        assert committed.json()["variant_count"] == 22

        replayed = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import",
            files={"file": ("catalog.csv", content, "text/csv")},
            data={"preview_sha256": preview.json()["payload_sha256"]},
            headers=commit_headers,
        )
        assert replayed.status_code == 200, replayed.text
        assert replayed.json()["replayed"] is True

        different = csv_bytes([csv_row(30)])
        mismatch = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import",
            files={"file": ("catalog.csv", different, "text/csv")},
            data={"preview_sha256": hashlib.sha256(different).hexdigest()},
            headers=commit_headers,
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["error"]["code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"

        pending_rows = [csv_row(40), csv_row(41)]
        pending_content = csv_bytes(pending_rows)
        pending_preview = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import/preview",
            files={"file": ("pending.csv", pending_content, "text/csv")},
            headers=csrf_headers(client),
        )
        assert pending_preview.json()["errors"] == []
        create_product(client, workspace["id"], sku="P-40", name="Concurrent product")
        rejected = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import",
            files={"file": ("pending.csv", pending_content, "text/csv")},
            data={"preview_sha256": pending_preview.json()["payload_sha256"]},
            headers={**csrf_headers(client), "Idempotency-Key": "revalidate-1"},
        )
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "IMPORT_VALIDATION_FAILED"
        rejected_replay = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import",
            files={"file": ("pending.csv", pending_content, "text/csv")},
            data={"preview_sha256": pending_preview.json()["payload_sha256"]},
            headers={**csrf_headers(client), "Idempotency-Key": "revalidate-1"},
        )
        assert rejected_replay.status_code == 422
        assert rejected_replay.json()["error"]["details"] == rejected.json()["error"]["details"]

    async def counts() -> tuple[int, int]:
        async with session_factory() as session:
            products = await session.scalar(select(func.count()).select_from(Product))
            variants = await session.scalar(select(func.count()).select_from(ProductVariant))
            assert products is not None and variants is not None
            return products, variants

    assert asyncio.run(counts()) == (22, 22)


def test_duplicate_variant_csv_and_live_import_claim_are_rejected(
    app_factory: AppFactory,
) -> None:
    app, session_factory, _ = app_factory()
    duplicate_content = csv_bytes([csv_row(1), {**csv_row(2), "variant_sku": "V-1"}])
    with TestClient(app) as client:
        workspace = register_and_create_workspace(client, "owner@example.com", "shop")
        preview = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import/preview",
            files={"file": ("catalog.csv", duplicate_content, "text/csv")},
            headers=csrf_headers(client),
        )
        assert preview.status_code == 200
        assert preview.json()["errors"][0]["code"] == "DUPLICATE_VARIANT_SKU"

        content = csv_bytes([csv_row(5)])
        payload_sha256 = hashlib.sha256(content).hexdigest()

        async def add_live_claim() -> None:
            async with session_factory() as session, session.begin():
                session.add(
                    CatalogImport(
                        workspace_id=UUID(workspace["id"]),
                        idempotency_key="concurrent-1",
                        payload_sha256=payload_sha256,
                        status="processing",
                        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                    )
                )

        asyncio.run(add_live_claim())
        conflict = client.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/import",
            files={"file": ("catalog.csv", content, "text/csv")},
            data={"preview_sha256": payload_sha256},
            headers={**csrf_headers(client), "Idempotency-Key": "concurrent-1"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IMPORT_IN_PROGRESS"


def test_cursor_pagination_uses_stable_created_at_and_id_order(app_factory: AppFactory) -> None:
    app, _, _ = app_factory()
    with TestClient(app) as client:
        workspace = register_and_create_workspace(client, "owner@example.com", "shop")
        for index in range(4):
            create_product(client, workspace["id"], sku=f"SKU-{index}", name=f"Product {index}")
        first = client.get(f"/api/v1/workspaces/{workspace['id']}/products", params={"limit": 2})
        assert first.status_code == 200
        assert first.json()["next_cursor"] is not None
        second = client.get(
            f"/api/v1/workspaces/{workspace['id']}/products",
            params={"limit": 2, "cursor": first.json()["next_cursor"]},
        )
        first_ids = {item["id"] for item in first.json()["items"]}
        second_ids = {item["id"] for item in second.json()["items"]}
        assert len(first_ids) == len(second_ids) == 2
        assert first_ids.isdisjoint(second_ids)
