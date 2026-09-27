import asyncio
import os
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from agent_hub_api.agents.models import Agent, AgentCatalogCollection, AgentLocation
from agent_hub_api.catalog.models import (
    CatalogCollection,
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
TEST_SCHEMA = "agenthub_test"
API_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(API_ROOT.parents[1] / ".env", override=False)


def require_database_url() -> str:
    if os.getenv("RUN_POSTGRES_INTEGRATION_TESTS", "").casefold() != "true":
        pytest.skip("Set RUN_POSTGRES_INTEGRATION_TESTS=true to run destructive schema tests")
    if os.getenv("APP_ENV", "local").casefold() not in {"local", "test"}:
        pytest.fail("PostgreSQL integration tests only run when APP_ENV is local or test")
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        pytest.skip("DATABASE_URL is not configured")
    return normalize_database_url(raw_url)


def migrate(revision: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes["target_schema"] = TEST_SCHEMA
    command.upgrade(config, revision)


def downgrade(revision: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes["target_schema"] = TEST_SCHEMA
    command.downgrade(config, revision)


def reset_test_schema(database_url: str, *, create: bool) -> None:
    async def reset() -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE')
                if create:
                    await connection.exec_driver_sql(f'CREATE SCHEMA "{TEST_SCHEMA}"')
        finally:
            await engine.dispose()

    asyncio.run(reset())


def schema_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
    )


def test_postgres_jsonb_uniqueness_transaction_and_tenant_scope() -> None:
    database_url = require_database_url()
    reset_test_schema(database_url, create=True)
    migrate("head")

    async def exercise() -> None:
        engine = schema_engine(database_url)
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
                    location_b = Location(
                        workspace_id=workspace_b,
                        name="Other PostgreSQL test",
                        code="PG-OTHER",
                        type="store",
                    )
                    collection_a = CatalogCollection(
                        workspace_id=workspace_a,
                        name="PG collection A",
                    )
                    collection_b = CatalogCollection(
                        workspace_id=workspace_b,
                        name="PG collection B",
                    )
                    agent = Agent(
                        public_id=new_uuid_v7(),
                        workspace_id=workspace_a,
                        name="PG agent",
                        created_by_user_id=user_id,
                    )
                    session.add_all(
                        [
                            variant,
                            location,
                            location_b,
                            collection_a,
                            collection_b,
                            agent,
                        ]
                    )
                    await session.flush()

                    invalid_location_assignment = await session.begin_nested()
                    session.add(
                        AgentLocation(
                            workspace_id=workspace_a,
                            agent_id=agent.id,
                            location_id=location_b.id,
                        )
                    )
                    with pytest.raises(IntegrityError):
                        await session.flush()
                    await invalid_location_assignment.rollback()

                    invalid_collection_assignment = await session.begin_nested()
                    session.add(
                        AgentCatalogCollection(
                            workspace_id=workspace_a,
                            agent_id=agent.id,
                            collection_id=collection_b.id,
                        )
                    )
                    with pytest.raises(IntegrityError):
                        await session.flush()
                    await invalid_collection_assignment.rollback()
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

    try:
        asyncio.run(exercise())
    finally:
        reset_test_schema(database_url, create=False)


def test_agent_migration_round_trip_in_isolated_schema() -> None:
    database_url = require_database_url()
    reset_test_schema(database_url, create=True)
    try:
        migrate("head")

        async def table_exists(table_name: str) -> bool:
            engine = schema_engine(database_url)
            try:
                async with engine.connect() as connection:
                    value = await connection.scalar(
                        text("SELECT to_regclass(:qualified_name)"),
                        {"qualified_name": f"{TEST_SCHEMA}.{table_name}"},
                    )
                    return value is not None
            finally:
                await engine.dispose()

        assert asyncio.run(table_exists("agents"))
        assert asyncio.run(table_exists("agent_locations"))
        assert asyncio.run(table_exists("agent_catalog_collections"))

        downgrade("20260925_0005")
        assert not asyncio.run(table_exists("agents"))
        assert not asyncio.run(table_exists("agent_locations"))
        assert not asyncio.run(table_exists("agent_catalog_collections"))

        migrate("head")
        assert asyncio.run(table_exists("agents"))
    finally:
        reset_test_schema(database_url, create=False)


def test_location_migration_backfills_stock_in_isolated_schema() -> None:
    database_url = require_database_url()
    reset_test_schema(database_url, create=True)
    try:
        migrate("20260925_0004")

        async def seed_pre_location_catalog() -> None:
            engine = schema_engine(database_url)
            try:
                workspace_id = new_uuid_v7()
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO workspaces (id, slug, display_name, status)
                            VALUES (:workspace_id, 'migration-test', 'Migration test', 'active')
                            """
                        ),
                        {"workspace_id": workspace_id},
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO products (
                                workspace_id, product_sku, name, currency, price,
                                stock_quantity, inventory_policy, attributes_json, status
                            ) VALUES (
                                :workspace_id, 'MIGRATION-SKU', 'Migration product', 'VND', 100,
                                7, 'tracked', '{}'::jsonb, 'active'
                            )
                            """
                        ),
                        {"workspace_id": workspace_id},
                    )
            finally:
                await engine.dispose()

        asyncio.run(seed_pre_location_catalog())
        migrate("head")

        async def verify_backfill() -> None:
            engine = schema_engine(database_url)
            try:
                async with engine.connect() as connection:
                    row = (
                        await connection.execute(
                            text(
                                """
                                SELECT l.code, v.attributes_json ->> 'system_default', i.quantity
                                FROM products p
                                JOIN product_variants v
                                  ON v.workspace_id = p.workspace_id AND v.product_id = p.id
                                JOIN inventory_levels i
                                  ON i.workspace_id = v.workspace_id AND i.variant_id = v.id
                                JOIN locations l
                                  ON l.workspace_id = i.workspace_id AND l.id = i.location_id
                                WHERE p.product_sku = 'MIGRATION-SKU'
                                """
                            )
                        )
                    ).one()
                    assert tuple(row) == ("DEFAULT", "true", 7)
            finally:
                await engine.dispose()

        asyncio.run(verify_backfill())
    finally:
        reset_test_schema(database_url, create=False)
