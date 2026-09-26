import asyncio
import os
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from agent_hub_api.catalog.models import (
    InventoryLevel,
    Location,
    LocationVariant,
    Product,
    ProductVariant,
)
from agent_hub_api.core.config import normalize_database_url
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.models import Workspace, WorkspaceMember

pytestmark = pytest.mark.postgres


def test_postgres_jsonb_uniqueness_transaction_and_tenant_scope() -> None:
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    async def exercise() -> None:
        engine = create_async_engine(normalize_database_url(raw_url))
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                session = AsyncSession(bind=connection, expire_on_commit=False)
                try:
                    user_id = new_uuid_v7()
                    workspace_a = new_uuid_v7()
                    workspace_b = new_uuid_v7()
                    session.add(
                        User(
                            id=user_id,
                            normalized_email=f"pg-{user_id}@example.test",
                            password_hash="test",
                            email_verified_at=None,
                            status="active",
                        )
                    )
                    session.add_all(
                        [
                            Workspace(
                                id=workspace_a,
                                slug=f"pg-a-{workspace_a}",
                                display_name="A",
                                status="active",
                            ),
                            Workspace(
                                id=workspace_b,
                                slug=f"pg-b-{workspace_b}",
                                display_name="B",
                                status="active",
                            ),
                            WorkspaceMember(
                                workspace_id=workspace_a, user_id=user_id, role="owner"
                            ),
                        ]
                    )
                    await session.flush()
                    product_a = Product(
                        workspace_id=workspace_a,
                        product_sku="PG-SKU",
                        name="A",
                        currency="VND",
                        price=Decimal("10"),
                        attributes_json={"material": "cotton"},
                    )
                    product_b = Product(
                        workspace_id=workspace_b,
                        product_sku="PG-SKU",
                        name="B",
                        currency="VND",
                        price=Decimal("20"),
                        attributes_json={"material": "linen"},
                    )
                    session.add_all([product_a, product_b])
                    await session.flush()
                    variant = ProductVariant(
                        workspace_id=workspace_a,
                        product_id=product_a.id,
                        variant_sku="PG-VARIANT",
                        attributes_json={"fragile": False},
                    )
                    location = Location(
                        workspace_id=workspace_a,
                        name="PostgreSQL test",
                        code="PG-TEST",
                        type="store",
                    )
                    session.add_all([variant, location])
                    await session.flush()
                    session.add_all(
                        [
                            LocationVariant(
                                workspace_id=workspace_a,
                                location_id=location.id,
                                variant_id=variant.id,
                            ),
                            InventoryLevel(
                                workspace_id=workspace_a,
                                location_id=location.id,
                                variant_id=variant.id,
                                quantity=0,
                            ),
                        ]
                    )
                    await session.flush()

                    cotton = list(
                        (
                            await session.scalars(
                                select(Product).where(
                                    Product.workspace_id == workspace_a,
                                    Product.attributes_json["material"].as_string() == "cotton",
                                )
                            )
                        ).all()
                    )
                    assert [product.id for product in cotton] == [product_a.id]
                    leaked = list(
                        (
                            await session.scalars(
                                select(Product).where(
                                    Product.workspace_id == workspace_a, Product.id == product_b.id
                                )
                            )
                        ).all()
                    )
                    assert leaked == []

                    nested = await session.begin_nested()
                    session.add(
                        Product(
                            workspace_id=workspace_a,
                            product_sku="PG-SKU",
                            name="Duplicate",
                            currency="VND",
                            attributes_json={},
                        )
                    )
                    with pytest.raises(IntegrityError):
                        await session.flush()
                    await nested.rollback()
                finally:
                    await session.close()
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(exercise())
