import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agent_hub_api.catalog.models import (
    CatalogCollection,
    CatalogCollectionProduct,
    InventoryLevel,
    Location,
    LocationVariant,
    Product,
    ProductVariant,
)
from agent_hub_api.catalog.read_models import AuthorizedCatalogScope, CatalogQuery
from agent_hub_api.catalog.read_service import CatalogReadService
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import Workspace


def test_product_centric_search_batches_rows_and_enforces_authorized_scope(
    tmp_path: Path,
) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog-read.db'}")
        query_count = 0

        def count_query(*_: object) -> None:
            nonlocal query_count
            query_count += 1

        event.listen(engine.sync_engine, "before_cursor_execute", count_query)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                workspace_id = new_uuid_v7()
                other_workspace_id = new_uuid_v7()
                session.add_all(
                    [
                        Workspace(
                            id=workspace_id,
                            slug="catalog-read",
                            display_name="Catalog read",
                            status="active",
                        ),
                        Workspace(
                            id=other_workspace_id,
                            slug="other-catalog-read",
                            display_name="Other",
                            status="active",
                        ),
                    ]
                )
                now = datetime.now(UTC)
                product = Product(
                    workspace_id=workspace_id,
                    product_sku="SHIRT",
                    name="Shirt",
                    currency="VND",
                    price=Decimal("100"),
                    status="active",
                    updated_at=now,
                )
                other_product = Product(
                    workspace_id=workspace_id,
                    product_sku="PANTS",
                    name="Pants",
                    currency="VND",
                    price=Decimal("200"),
                    status="active",
                    updated_at=now - timedelta(seconds=1),
                )
                session.add_all([product, other_product])
                await session.flush()
                variant = ProductVariant(
                    workspace_id=workspace_id,
                    product_id=product.id,
                    variant_sku="SHIRT-M",
                    inventory_policy="tracked",
                    status="active",
                )
                sibling_variant = ProductVariant(
                    workspace_id=workspace_id,
                    product_id=product.id,
                    variant_sku="SHIRT-L",
                    inventory_policy="tracked",
                    status="active",
                )
                other_variant = ProductVariant(
                    workspace_id=workspace_id,
                    product_id=other_product.id,
                    variant_sku="PANTS-M",
                    inventory_policy="tracked",
                    status="active",
                )
                hanoi = Location(
                    workspace_id=workspace_id,
                    name="Hà Nội",
                    code="HN",
                    type="store",
                )
                saigon = Location(
                    workspace_id=workspace_id,
                    name="Sài Gòn",
                    code="SG",
                    type="store",
                )
                session.add_all([variant, sibling_variant, other_variant, hanoi, saigon])
                await session.flush()
                summer = CatalogCollection(
                    workspace_id=workspace_id,
                    name="Summer",
                    is_active=True,
                )
                other_collection = CatalogCollection(
                    workspace_id=workspace_id,
                    name="Other",
                    is_active=True,
                )
                session.add_all([summer, other_collection])
                await session.flush()
                session.add_all(
                    [
                        CatalogCollectionProduct(
                            workspace_id=workspace_id,
                            collection_id=summer.id,
                            product_id=product.id,
                        ),
                        CatalogCollectionProduct(
                            workspace_id=workspace_id,
                            collection_id=other_collection.id,
                            product_id=other_product.id,
                        ),
                        LocationVariant(
                            workspace_id=workspace_id,
                            location_id=hanoi.id,
                            variant_id=variant.id,
                            price_override=Decimal("90"),
                        ),
                        LocationVariant(
                            workspace_id=workspace_id,
                            location_id=saigon.id,
                            variant_id=variant.id,
                            price_override=Decimal("110"),
                        ),
                        LocationVariant(
                            workspace_id=workspace_id,
                            location_id=hanoi.id,
                            variant_id=sibling_variant.id,
                        ),
                        LocationVariant(
                            workspace_id=workspace_id,
                            location_id=hanoi.id,
                            variant_id=other_variant.id,
                        ),
                        InventoryLevel(
                            workspace_id=workspace_id,
                            location_id=hanoi.id,
                            variant_id=variant.id,
                            quantity=2,
                        ),
                        InventoryLevel(
                            workspace_id=workspace_id,
                            location_id=saigon.id,
                            variant_id=variant.id,
                            quantity=None,
                        ),
                        InventoryLevel(
                            workspace_id=workspace_id,
                            location_id=hanoi.id,
                            variant_id=sibling_variant.id,
                            quantity=0,
                        ),
                        InventoryLevel(
                            workspace_id=workspace_id,
                            location_id=hanoi.id,
                            variant_id=other_variant.id,
                            quantity=0,
                        ),
                    ]
                )
                await session.commit()

                scope = AuthorizedCatalogScope(
                    workspace_id=workspace_id,
                    allowed_location_ids=frozenset({hanoi.id, saigon.id}),
                    allowed_collection_ids=frozenset({summer.id, other_collection.id}),
                )
                query_count = 0
                products = await CatalogReadService(session).search_products(
                    scope,
                    CatalogQuery(
                        requested_location_ids=frozenset({hanoi.id, saigon.id}),
                        requested_collection_ids=frozenset({summer.id}),
                        limit=1,
                    ),
                )
                assert query_count == 7
                assert [item.id for item in products] == [product.id]
                assert products[0].price.kind == "range"
                assert products[0].price.minimum == Decimal("90")
                assert products[0].price.maximum == Decimal("110")
                assert products[0].availability.in_stock_locations == 1
                assert products[0].availability.unknown_locations == 1
                assert products[0].availability.total_locations == 2
                assert len(products[0].variants) == 2
                assert len(products[0].variants[0].availability) == 2
                assert await CatalogReadService(session).has_products(scope) is True
                assert (
                    await CatalogReadService(session).has_products(
                        AuthorizedCatalogScope(
                            workspace_id=workspace_id,
                            allowed_location_ids=frozenset({hanoi.id}),
                            allowed_collection_ids=frozenset(),
                        )
                    )
                    is False
                )
                assert (
                    await CatalogReadService(session).has_products(
                        AuthorizedCatalogScope(
                            workspace_id=other_workspace_id,
                            allowed_location_ids=None,
                            allowed_collection_ids=None,
                        )
                    )
                    is False
                )

                with pytest.raises(ApiError) as denied:
                    await CatalogReadService(session).search_products(
                        AuthorizedCatalogScope(
                            workspace_id=workspace_id,
                            allowed_location_ids=frozenset({hanoi.id}),
                        ),
                        CatalogQuery(requested_location_ids=frozenset({saigon.id})),
                    )
                assert denied.value.status_code == 404

                leaked = await CatalogReadService(session).search_products(
                    AuthorizedCatalogScope(workspace_id=other_workspace_id),
                    CatalogQuery(),
                )
                assert leaked == ()
        finally:
            await engine.dispose()

    asyncio.run(exercise())
