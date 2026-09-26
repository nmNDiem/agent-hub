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


def test_location_inventory_price_collections_and_tenant_scope(
    app_factory: AppFactory,
) -> None:
    app, _, _ = app_factory()
    with TestClient(app) as client:
        workspace = register_and_create_workspace(client, "scope@example.com", "scope-shop")
        workspace_id = workspace["id"]
        product = create_product(client, workspace_id, price="100.00")
        variant_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/products/{product['id']}/variants",
            json={"variant_sku": "SCOPE-V1", "price_override": "120.00", "stock_quantity": 0},
            headers=csrf_headers(client),
        )
        assert variant_response.status_code == 201, variant_response.text
        variant = variant_response.json()
        assert variant["stock_quantity"] == 0
        assert variant["availability"][0]["location_code"] == "DEFAULT"
        default_location_id = variant["availability"][0]["location_id"]
        default_search = client.get(
            f"/api/v1/workspaces/{workspace_id}/catalog/search",
            params={"location_id": default_location_id},
        )
        assert default_search.status_code == 200, default_search.text
        assert default_search.json()["items"][0]["effective_price"] == "120.00"

        def create_location(name: str, code: str) -> dict[str, Any]:
            response = client.post(
                f"/api/v1/workspaces/{workspace_id}/locations",
                json={"name": name, "code": code, "type": "store"},
                headers=csrf_headers(client),
            )
            assert response.status_code == 201, response.text
            return cast(dict[str, Any], response.json())

        hcm = create_location("Hồ Chí Minh", "HCM")
        hanoi = create_location("Hà Nội", "HN")
        hcm_inventory = client.put(
            f"/api/v1/workspaces/{workspace_id}/locations/{hcm['id']}/variants/{variant['id']}",
            json={"quantity": None, "price_override": "90.00"},
            headers=csrf_headers(client),
        )
        assert hcm_inventory.status_code == 200, hcm_inventory.text
        assert hcm_inventory.json()["quantity"] is None
        assert hcm_inventory.json()["effective_price"] == "90.00"
        hanoi_inventory = client.put(
            f"/api/v1/workspaces/{workspace_id}/locations/{hanoi['id']}/variants/{variant['id']}",
            json={"quantity": 0, "price_override": "110.00"},
            headers=csrf_headers(client),
        )
        assert hanoi_inventory.status_code == 200, hanoi_inventory.text
        assert hanoi_inventory.json()["quantity"] == 0

        hcm_search = client.get(
            f"/api/v1/workspaces/{workspace_id}/catalog/search",
            params={"location_id": hcm["id"]},
        )
        assert hcm_search.status_code == 200, hcm_search.text
        assert hcm_search.json()["items"][0]["effective_price"] == "90.00"
        assert hcm_search.json()["items"][0]["stock_quantity"] is None

        collection = client.post(
            f"/api/v1/workspaces/{workspace_id}/catalog/collections",
            json={"name": "Featured"},
            headers=csrf_headers(client),
        )
        assert collection.status_code == 201, collection.text
        collection_id = collection.json()["id"]
        assigned = client.put(
            f"/api/v1/workspaces/{workspace_id}/catalog/collections/{collection_id}/products/{product['id']}",
            headers=csrf_headers(client),
        )
        assert assigned.status_code == 204, assigned.text
        collection_products = client.get(
            f"/api/v1/workspaces/{workspace_id}/catalog/collections/{collection_id}/products"
        )
        assert collection_products.status_code == 200, collection_products.text
        assert [item["id"] for item in collection_products.json()] == [product["id"]]
        second_collection = client.post(
            f"/api/v1/workspaces/{workspace_id}/catalog/collections",
            json={"name": "Sale"},
            headers=csrf_headers(client),
        )
        assert second_collection.status_code == 201, second_collection.text
        assert (
            client.put(
                f"/api/v1/workspaces/{workspace_id}/catalog/collections/{second_collection.json()['id']}/products/{product['id']}",
                headers=csrf_headers(client),
            ).status_code
            == 204
        )
        scoped_search = client.get(
            f"/api/v1/workspaces/{workspace_id}/catalog/search",
            params={"location_id": hanoi["id"], "collection_id": collection_id},
        )
        assert scoped_search.status_code == 200, scoped_search.text
        assert [item["id"] for item in scoped_search.json()["items"]] == [product["id"]]
        deactivated = client.put(
            f"/api/v1/workspaces/{workspace_id}/locations/{hanoi['id']}/variants/{variant['id']}",
            json={"is_active": False},
            headers=csrf_headers(client),
        )
        assert deactivated.status_code == 200, deactivated.text
        hidden = client.get(
            f"/api/v1/workspaces/{workspace_id}/catalog/search",
            params={"location_id": hanoi["id"]},
        )
        assert hidden.json()["items"] == []

        other_workspace = client.post(
            "/api/v1/workspaces",
            json={"display_name": "Other", "slug": "other-scope-shop"},
            headers=csrf_headers(client),
        )
        assert other_workspace.status_code == 201, other_workspace.text
        cross_workspace = client.put(
            f"/api/v1/workspaces/{other_workspace.json()['id']}/locations/{hcm['id']}/variants/{variant['id']}",
            json={"quantity": 99},
            headers=csrf_headers(client),
        )
        assert cross_workspace.status_code == 404
        cross_collection = client.put(
            f"/api/v1/workspaces/{other_workspace.json()['id']}/catalog/collections/{collection_id}/products/{product['id']}",
            headers=csrf_headers(client),
        )
        assert cross_collection.status_code == 404

        archived = client.delete(
            f"/api/v1/workspaces/{workspace_id}/locations/{hcm['id']}",
            headers=csrf_headers(client),
        )
        assert archived.status_code == 204
        assert (
            client.get(f"/api/v1/workspaces/{workspace_id}/products/{product['id']}").status_code
            == 200
        )


def test_location_aware_import_does_not_duplicate_product_or_variant(
    app_factory: AppFactory,
) -> None:
    app, _, _ = app_factory()
    with TestClient(app) as client:
        workspace = register_and_create_workspace(
            client, "location-import@example.com", "location-import"
        )
        workspace_id = workspace["id"]
        locations: dict[str, int] = {}
        for code in ("HCM", "HN"):
            response = client.post(
                f"/api/v1/workspaces/{workspace_id}/locations",
                json={"name": code, "code": code, "type": "store"},
                headers=csrf_headers(client),
            )
            assert response.status_code == 201, response.text
            locations[code] = response.json()["id"]
        content = (
            b"Handle,Name,SKU,Location Code,Price,Quantity\n"
            b"shirt,Shirt,SHIRT-M,HCM,100,NULL\n"
            b"shirt,,SHIRT-M,HN,120,0\n"
        )
        analyzed = client.post(
            f"/api/v1/workspaces/{workspace_id}/catalog/imports",
            files={"file": ("locations.csv", content, "text/csv")},
            headers=csrf_headers(client),
        )
        assert analyzed.status_code == 201, analyzed.text
        assert analyzed.json()["status"] == "ready", analyzed.text
        assert analyzed.json()["summary"]["variants"]["create"] == 1
        committed = client.post(
            f"/api/v1/workspaces/{workspace_id}/catalog/imports/{analyzed.json()['id']}/commit",
            headers={**csrf_headers(client), "Idempotency-Key": "location-import-1"},
        )
        assert committed.status_code == 200, committed.text
        assert committed.json()["products_created"] == 1
        assert committed.json()["variants_created"] == 1
        assert committed.json()["variants_unchanged"] == 0
        for code, expected_price, expected_quantity in (
            ("HCM", "100.00", None),
            ("HN", "120.00", 0),
        ):
            search = client.get(
                f"/api/v1/workspaces/{workspace_id}/catalog/search",
                params={"location_id": locations[code]},
            )
            assert search.status_code == 200, search.text
            assert len(search.json()["items"]) == 1
            assert search.json()["items"][0]["effective_price"] == expected_price
            assert search.json()["items"][0]["stock_quantity"] == expected_quantity

        unknown = client.post(
            f"/api/v1/workspaces/{workspace_id}/catalog/imports",
            files={
                "file": (
                    "unknown.csv",
                    b"Handle,Name,SKU,Location Code,Quantity\nshirt-2,Shirt 2,S-2,UNKNOWN,2\n",
                    "text/csv",
                )
            },
            headers=csrf_headers(client),
        )
        assert unknown.status_code == 201, unknown.text
        assert unknown.json()["status"] == "needs_confirmation"
        assert any(issue["issue_type"] == "UNKNOWN_LOCATION" for issue in unknown.json()["issues"])


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

        generic = client.post(
            f"/api/v1/workspaces/{workspace['id']}/products/{product['id']}/variants",
            json={
                "variant_sku": "GENERIC-1",
                "options": {"Storage": "256GB", "Color": "Black"},
            },
            headers=csrf_headers(client),
        )
        assert generic.status_code == 201, generic.text
        assert generic.json()["color"] == "Black"
        assert generic.json()["options"] == {"Storage": "256GB", "Color": "Black"}
        detail = client.get(f"/api/v1/workspaces/{workspace['id']}/products/{product['id']}")
        generic_detail = next(
            item for item in detail.json()["variants"] if item["variant_sku"] == "GENERIC-1"
        )
        assert generic_detail["options"]["Storage"] == "256GB"

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


def test_universal_import_commit_and_option_search_are_tenant_scoped(
    app_factory: AppFactory,
) -> None:
    app, _, _ = app_factory()
    output = io.StringIO(newline="")
    columns = [
        "Handle",
        "Name",
        "SKU",
        "Option1 Name",
        "Option1 Value",
        "Option2 Name",
        "Option2 Value",
        "Price",
        "Quantity",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerow(
        {
            "Handle": "shirt",
            "Name": "Shirt",
            "SKU": "RED-M",
            "Option1 Name": "Color",
            "Option1 Value": "Red",
            "Option2 Name": "Size",
            "Option2 Value": "M",
            "Price": "100",
            "Quantity": "0",
        }
    )
    writer.writerow(
        {
            "Handle": "shirt",
            "SKU": "BLUE-L",
            "Option1 Name": "Color",
            "Option1 Value": "Blue",
            "Option2 Name": "Size",
            "Option2 Value": "L",
            "Price": "120",
            "Quantity": "3",
        }
    )
    content = output.getvalue().encode()

    with TestClient(app) as owner, TestClient(app) as stranger:
        workspace = register_and_create_workspace(owner, "universal@example.com", "universal")
        created = owner.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/imports",
            files={"file": ("catalog.csv", content, "text/csv")},
            headers=csrf_headers(owner),
        )
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "ready"
        assert created.json()["summary"]["products"]["create"] == 1
        import_id = created.json()["id"]

        register_and_create_workspace(stranger, "stranger@example.com", "stranger")
        denied = stranger.get(f"/api/v1/workspaces/{workspace['id']}/catalog/imports/{import_id}")
        assert denied.status_code == 404

        committed = owner.post(
            f"/api/v1/workspaces/{workspace['id']}/catalog/imports/{import_id}/commit",
            headers={**csrf_headers(owner), "Idempotency-Key": "universal-1"},
        )
        assert committed.status_code == 200, committed.text
        assert committed.json()["products_created"] == 1
        assert committed.json()["variants_created"] == 2

        exact = owner.get(
            f"/api/v1/workspaces/{workspace['id']}/catalog/search",
            params=[("option", "Color:Red"), ("option", "Size:M")],
        )
        assert exact.status_code == 200, exact.text
        assert [item["variant_sku"] for item in exact.json()["items"]] == ["RED-M"]

        impossible = owner.get(
            f"/api/v1/workspaces/{workspace['id']}/catalog/search",
            params=[("option", "Color:Red"), ("option", "Size:L")],
        )
        assert impossible.status_code == 200
        assert impossible.json()["items"] == []
