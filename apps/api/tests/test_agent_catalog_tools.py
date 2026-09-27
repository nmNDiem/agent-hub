import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agent_hub_api.agents.catalog_tools import AgentCatalogTools
from agent_hub_api.agents.models import Agent, AgentCatalogCollection, AgentLocation
from agent_hub_api.agents.service import resolve_agent_catalog_scope
from agent_hub_api.agents.tool_schemas import (
    CheckStockToolInput,
    GetProductDetailToolInput,
    SearchProductsToolInput,
)
from agent_hub_api.catalog.models import (
    CatalogCollection,
    CatalogCollectionProduct,
    InventoryLevel,
    Location,
    LocationVariant,
    Product,
    ProductImage,
    ProductOptionDefinition,
    ProductOptionValue,
    ProductVariant,
    SizeGuide,
    VariantOptionValue,
)
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.models import User
from agent_hub_api.models import Base
from agent_hub_api.workspaces.models import Workspace


def test_agent_catalog_tools_enforce_scope_and_preserve_catalog_facts(tmp_path: Path) -> None:
    async def exercise() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agent-tools.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                workspace_id = new_uuid_v7()
                other_workspace_id = new_uuid_v7()
                user_id = new_uuid_v7()
                user = User(
                    id=user_id,
                    normalized_email="tools@example.test",
                    password_hash="test",
                    status="active",
                )
                session.add_all(
                    [
                        user,
                        Workspace(
                            id=workspace_id,
                            slug="agent-tools",
                            display_name="Agent tools",
                            status="active",
                        ),
                        Workspace(
                            id=other_workspace_id,
                            slug="other-agent-tools",
                            display_name="Other",
                            status="active",
                        ),
                    ]
                )
                await session.flush()

                hanoi = Location(
                    workspace_id=workspace_id, name="Hanoi", code="HN", type="store"
                )
                saigon = Location(
                    workspace_id=workspace_id, name="Saigon", code="SG", type="store"
                )
                denied_location = Location(
                    workspace_id=workspace_id, name="Denied", code="DENIED", type="store"
                )
                allowed_collection = CatalogCollection(
                    workspace_id=workspace_id, name="Allowed", is_active=True
                )
                denied_collection = CatalogCollection(
                    workspace_id=workspace_id, name="Denied", is_active=True
                )
                session.add_all(
                    [
                        hanoi,
                        saigon,
                        denied_location,
                        allowed_collection,
                        denied_collection,
                    ]
                )
                await session.flush()

                false_match = Product(
                    workspace_id=workspace_id,
                    product_sku="FALSE-MATCH",
                    name="Cross variant only",
                    currency="VND",
                    price=Decimal("120"),
                    status="active",
                )
                actual_match = Product(
                    workspace_id=workspace_id,
                    product_sku="ACTUAL-MATCH",
                    name="Red medium shirt",
                    description="Verified description",
                    currency="VND",
                    price=Decimal("100"),
                    status="active",
                )
                leaked_product = Product(
                    workspace_id=other_workspace_id,
                    product_sku="ACTUAL-MATCH",
                    name="Other workspace product",
                    currency="VND",
                    price=Decimal("1"),
                    status="active",
                )
                session.add_all([false_match, actual_match, leaked_product])
                await session.flush()

                red_small = ProductVariant(
                    workspace_id=workspace_id,
                    product_id=false_match.id,
                    variant_sku="FALSE-RED-S",
                    inventory_policy="tracked",
                    status="active",
                )
                blue_medium = ProductVariant(
                    workspace_id=workspace_id,
                    product_id=false_match.id,
                    variant_sku="FALSE-BLUE-M",
                    inventory_policy="tracked",
                    status="active",
                )
                red_medium = ProductVariant(
                    workspace_id=workspace_id,
                    product_id=actual_match.id,
                    variant_sku="MATCH-RED-M",
                    color="stale legacy color",
                    size="stale legacy size",
                    inventory_policy="tracked",
                    status="active",
                )
                session.add_all([red_small, blue_medium, red_medium])
                await session.flush()

                for product, variants in (
                    (false_match, [(red_small, "Red", "S"), (blue_medium, "Blue", "M")]),
                    (actual_match, [(red_medium, "Red", "M")]),
                ):
                    color_definition = ProductOptionDefinition(
                        workspace_id=workspace_id,
                        product_id=product.id,
                        name="Color",
                        normalized_name="color",
                        position=0,
                    )
                    size_definition = ProductOptionDefinition(
                        workspace_id=workspace_id,
                        product_id=product.id,
                        name="Size",
                        normalized_name="size",
                        position=1,
                    )
                    session.add_all([color_definition, size_definition])
                    await session.flush()
                    for variant, color, size in variants:
                        color_value = ProductOptionValue(
                            workspace_id=workspace_id,
                            option_definition_id=color_definition.id,
                            value=color,
                            normalized_value=color.casefold(),
                        )
                        size_value = ProductOptionValue(
                            workspace_id=workspace_id,
                            option_definition_id=size_definition.id,
                            value=size,
                            normalized_value=size.casefold(),
                        )
                        session.add_all([color_value, size_value])
                        await session.flush()
                        session.add_all(
                            [
                                VariantOptionValue(
                                    workspace_id=workspace_id,
                                    variant_id=variant.id,
                                    option_value_id=color_value.id,
                                    option_definition_id=color_definition.id,
                                ),
                                VariantOptionValue(
                                    workspace_id=workspace_id,
                                    variant_id=variant.id,
                                    option_value_id=size_value.id,
                                    option_definition_id=size_definition.id,
                                ),
                            ]
                        )

                session.add_all(
                    [
                        CatalogCollectionProduct(
                            workspace_id=workspace_id,
                            collection_id=allowed_collection.id,
                            product_id=false_match.id,
                        ),
                        CatalogCollectionProduct(
                            workspace_id=workspace_id,
                            collection_id=allowed_collection.id,
                            product_id=actual_match.id,
                        ),
                    ]
                )
                for variant in (red_small, blue_medium, red_medium):
                    session.add(
                        LocationVariant(
                            workspace_id=workspace_id,
                            location_id=hanoi.id,
                            variant_id=variant.id,
                            price_override=(
                                Decimal("90") if variant.id == red_medium.id else None
                            ),
                        )
                    )
                    session.add(
                        InventoryLevel(
                            workspace_id=workspace_id,
                            location_id=hanoi.id,
                            variant_id=variant.id,
                            quantity=None,
                        )
                    )
                session.add_all(
                    [
                        LocationVariant(
                            workspace_id=workspace_id,
                            location_id=saigon.id,
                            variant_id=red_medium.id,
                            price_override=Decimal("0"),
                        ),
                        InventoryLevel(
                            workspace_id=workspace_id,
                            location_id=saigon.id,
                            variant_id=red_medium.id,
                            quantity=0,
                        ),
                        SizeGuide(
                            workspace_id=workspace_id,
                            product_id=actual_match.id,
                            title="Measurements",
                            content={"unit": "cm"},
                        ),
                        ProductImage(
                            workspace_id=workspace_id,
                            product_id=actual_match.id,
                            variant_id=red_medium.id,
                            object_key="workspaces/private/catalog/image.png",
                            alt_text="Managed image",
                            status="active",
                        ),
                        ProductImage(
                            workspace_id=workspace_id,
                            product_id=actual_match.id,
                            source_url="https://cdn.example.test/product.png",
                            alt_text="Remote image",
                            status="active",
                            sort_order=1,
                        ),
                        ProductImage(
                            workspace_id=workspace_id,
                            product_id=actual_match.id,
                            source_url="file:///private/image.png",
                            status="active",
                            sort_order=2,
                        ),
                    ]
                )
                agent = Agent(
                    public_id=new_uuid_v7(),
                    workspace_id=workspace_id,
                    name="Scoped agent",
                    all_locations=False,
                    all_collections=False,
                    created_by_user_id=user_id,
                )
                session.add(agent)
                await session.flush()
                session.add_all(
                    [
                        AgentLocation(
                            workspace_id=workspace_id,
                            agent_id=agent.id,
                            location_id=hanoi.id,
                        ),
                        AgentLocation(
                            workspace_id=workspace_id,
                            agent_id=agent.id,
                            location_id=saigon.id,
                        ),
                        AgentCatalogCollection(
                            workspace_id=workspace_id,
                            agent_id=agent.id,
                            collection_id=allowed_collection.id,
                        ),
                    ]
                )
                await session.commit()

                scope = await resolve_agent_catalog_scope(
                    session, workspace_id=workspace_id, public_agent_id=agent.public_id
                )
                assert scope.allowed_location_ids == frozenset({hanoi.id, saigon.id})
                assert scope.allowed_collection_ids == frozenset({allowed_collection.id})
                tools = AgentCatalogTools(session, scope)

                result = await tools.search_products(
                    SearchProductsToolInput(
                        options={"Color": "Red", "Size": "M"},
                        location_ids=[hanoi.id],
                        collection_ids=[allowed_collection.id],
                    )
                )
                assert [item.id for item in result.items] == [actual_match.id]
                item = result.items[0]
                assert item.price.kind == "exact"
                assert item.price.minimum == Decimal("90")
                assert item.availability.unknown_locations == 1
                assert item.variants[0].options == {"Color": "Red", "Size": "M"}
                assert item.variants[0].color == "Red"
                assert item.variants[0].size == "M"
                assert [image.kind for image in item.images] == ["managed", "remote"]
                assert "object_key" not in item.model_dump_json()
                assert "https://cdn.example.test" not in item.model_dump_json()
                assert item.size_guide is not None

                stock = await tools.check_stock(CheckStockToolInput(variant_id=red_medium.id))
                assert stock is not None
                assert stock.inventory_policy == "tracked"
                assert [value.inventory_state for value in stock.availability] == [
                    "unknown",
                    "out_of_stock",
                ]
                assert [value.effective_price for value in stock.availability] == [
                    Decimal("90"),
                    Decimal("0"),
                ]

                detail = await tools.get_product_detail(
                    GetProductDetailToolInput(product_id=actual_match.id)
                )
                assert detail is not None
                assert detail.description == "Verified description"
                assert detail.price.kind == "range"
                assert detail.price.minimum == Decimal("0")
                assert detail.price.maximum == Decimal("90")

                with pytest.raises(ApiError) as denied_location_error:
                    await tools.search_products(
                        SearchProductsToolInput(location_ids=[denied_location.id])
                    )
                assert denied_location_error.value.status_code == 404
                with pytest.raises(ApiError) as denied_collection_error:
                    await tools.search_products(
                        SearchProductsToolInput(collection_ids=[denied_collection.id])
                    )
                assert denied_collection_error.value.status_code == 404

                with pytest.raises(ApiError) as cross_workspace:
                    await resolve_agent_catalog_scope(
                        session,
                        workspace_id=other_workspace_id,
                        public_agent_id=agent.public_id,
                    )
                assert cross_workspace.value.status_code == 404

                hanoi.is_active = False
                saigon.is_active = False
                await session.commit()
                inactive_scope = await resolve_agent_catalog_scope(
                    session, workspace_id=workspace_id, public_agent_id=agent.public_id
                )
                assert inactive_scope.allowed_location_ids == frozenset()
                assert (
                    await AgentCatalogTools(session, inactive_scope).search_products(
                        SearchProductsToolInput()
                    )
                ).items == []
        finally:
            await engine.dispose()

    asyncio.run(exercise())
