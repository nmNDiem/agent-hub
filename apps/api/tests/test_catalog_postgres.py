import asyncio
import os
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
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
from agent_hub_api.knowledge.models import (
    AgentKnowledgeBase,
    EmbeddingProfile,
    IngestionJob,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeDocumentActiveGeneration,
    KnowledgeDocumentVersion,
    KnowledgeGeneration,
)
from agent_hub_api.knowledge.providers import (
    EmbeddingProfileSpec,
    VectorPoint,
    VectorSearchHit,
)
from agent_hub_api.knowledge.retrieval import (
    KnowledgeRetrievalService,
    resolve_agent_knowledge_scope,
)
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


def test_knowledge_constraints_fence_document_graph_in_postgres() -> None:
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
                    workspace_id = new_uuid_v7()
                    session.add(
                        User(
                            id=user_id,
                            normalized_email=f"knowledge-pg-{user_id}@example.test",
                            password_hash="test",
                            status="active",
                        )
                    )
                    session.add(
                        Workspace(
                            id=workspace_id,
                            slug=f"knowledge-pg-{workspace_id}",
                            display_name="Knowledge PostgreSQL",
                            status="active",
                        )
                    )
                    profile = EmbeddingProfile(
                        provider="test",
                        model="test-3d",
                        dimensions=3,
                        pipeline_version="test-v1",
                        distance_metric="cosine",
                        qdrant_collection=f"knowledge-{workspace_id}",
                        config_hash=f"{workspace_id.hex}{'0' * 32}",
                        status="active",
                    )
                    session.add(profile)
                    await session.flush()
                    knowledge_base = KnowledgeBase(
                        workspace_id=workspace_id,
                        name="Knowledge constraints",
                        kind="general",
                        active_embedding_profile_id=profile.id,
                    )
                    session.add(knowledge_base)
                    await session.flush()
                    document_a = KnowledgeDocument(
                        workspace_id=workspace_id,
                        knowledge_base_id=knowledge_base.id,
                        title="A",
                        kind="faq",
                    )
                    document_b = KnowledgeDocument(
                        workspace_id=workspace_id,
                        knowledge_base_id=knowledge_base.id,
                        title="B",
                        kind="faq",
                    )
                    session.add_all([document_a, document_b])
                    await session.flush()
                    version_a = KnowledgeDocumentVersion(
                        workspace_id=workspace_id,
                        document_id=document_a.id,
                        version_no=1,
                        source_kind="manual",
                        source_text="A",
                        content_sha256="a" * 64,
                        mime_type="text/plain",
                        byte_size=1,
                        created_by_user_id=user_id,
                    )
                    version_b = KnowledgeDocumentVersion(
                        workspace_id=workspace_id,
                        document_id=document_b.id,
                        version_no=1,
                        source_kind="manual",
                        source_text="B",
                        content_sha256="b" * 64,
                        mime_type="text/plain",
                        byte_size=1,
                        created_by_user_id=user_id,
                    )
                    session.add_all([version_a, version_b])
                    await session.flush()

                    invalid_generation = await session.begin_nested()
                    session.add(
                        KnowledgeGeneration(
                            workspace_id=workspace_id,
                            document_id=document_a.id,
                            document_version_id=version_b.id,
                            embedding_profile_id=profile.id,
                            generation_no=1,
                            chunker_version="test-v1",
                            chunk_size=100,
                            chunk_overlap=10,
                            pipeline_config_hash="c" * 64,
                        )
                    )
                    with pytest.raises(IntegrityError):
                        await session.flush()
                    await invalid_generation.rollback()

                    generation = KnowledgeGeneration(
                        workspace_id=workspace_id,
                        document_id=document_a.id,
                        document_version_id=version_a.id,
                        embedding_profile_id=profile.id,
                        generation_no=1,
                        chunker_version="test-v1",
                        chunk_size=100,
                        chunk_overlap=10,
                        pipeline_config_hash="d" * 64,
                    )
                    session.add(generation)
                    await session.flush()
                    first_job = IngestionJob(
                        workspace_id=workspace_id,
                        document_id=document_a.id,
                        document_version_id=version_a.id,
                        target_generation_id=generation.id,
                        status="queued",
                        idempotency_key="first",
                        request_sha256="e" * 64,
                    )
                    session.add(first_job)
                    await session.flush()

                    duplicate_active_job = await session.begin_nested()
                    session.add(
                        IngestionJob(
                            workspace_id=workspace_id,
                            document_id=document_a.id,
                            document_version_id=version_a.id,
                            target_generation_id=generation.id,
                            status="retry_scheduled",
                            idempotency_key="second",
                            request_sha256="f" * 64,
                        )
                    )
                    with pytest.raises(IntegrityError):
                        await session.flush()
                    await duplicate_active_job.rollback()

                    wrong_document_job = await session.begin_nested()
                    session.add(
                        IngestionJob(
                            workspace_id=workspace_id,
                            document_id=document_b.id,
                            document_version_id=version_b.id,
                            target_generation_id=generation.id,
                            status="queued",
                            idempotency_key="wrong-generation",
                            request_sha256="1" * 64,
                        )
                    )
                    with pytest.raises(IntegrityError):
                        await session.flush()
                    await wrong_document_job.rollback()

                    immutable_profile = await session.begin_nested()
                    with pytest.raises(DBAPIError):
                        await session.execute(
                            update(EmbeddingProfile)
                            .where(EmbeddingProfile.id == profile.id)
                            .values(model="mutated")
                        )
                    await immutable_profile.rollback()
                finally:
                    await session.close()
                    await transaction.rollback()
        finally:
            await engine.dispose()

    try:
        asyncio.run(exercise())
    finally:
        reset_test_schema(database_url, create=False)


def test_knowledge_retrieval_revalidates_active_generation_in_postgres() -> None:
    database_url = require_database_url()
    reset_test_schema(database_url, create=True)
    migrate("head")

    class FakeEmbeddingProvider:
        async def embed(
            self, profile: EmbeddingProfileSpec, texts: list[str]
        ) -> list[tuple[float, ...]]:
            return [(1.0, 0.0, 0.0) for _ in texts]

    class FakeVectorIndex:
        def __init__(self, hit: VectorSearchHit) -> None:
            self.hit = hit

        async def ensure_profile(self, profile: EmbeddingProfileSpec) -> None:
            pass

        async def upsert(
            self, profile: EmbeddingProfileSpec, points: list[VectorPoint]
        ) -> None:
            pass

        async def search(
            self,
            profile: EmbeddingProfileSpec,
            vector: tuple[float, ...],
            *,
            workspace_id: UUID,
            allowed_knowledge_base_ids: tuple[int, ...],
            limit: int,
        ) -> list[VectorSearchHit]:
            return [self.hit]

        async def delete(
            self, profile: EmbeddingProfileSpec, point_ids: list[UUID]
        ) -> None:
            pass

    async def exercise() -> None:
        engine = schema_engine(database_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                session = AsyncSession(bind=connection, expire_on_commit=False)
                try:
                    user_id = new_uuid_v7()
                    workspace_id = new_uuid_v7()
                    agent_public_id = new_uuid_v7()
                    point_id = uuid4()
                    session.add(
                        User(
                            id=user_id,
                            normalized_email=f"retrieval-pg-{user_id}@example.test",
                            password_hash="test",
                            status="active",
                        )
                    )
                    session.add(
                        Workspace(
                            id=workspace_id,
                            slug=f"retrieval-pg-{workspace_id}",
                            display_name="Retrieval PostgreSQL",
                            status="active",
                        )
                    )
                    profile = EmbeddingProfile(
                        provider="openai",
                        model="test-3d",
                        dimensions=3,
                        pipeline_version="test-v1",
                        distance_metric="cosine",
                        qdrant_collection=f"retrieval-pg-{workspace_id}",
                        config_hash=f"{workspace_id.hex}{'0' * 32}",
                        status="active",
                    )
                    session.add(profile)
                    await session.flush()
                    knowledge_base = KnowledgeBase(
                        workspace_id=workspace_id,
                        name="Retrieval base",
                        kind="general",
                        active_embedding_profile_id=profile.id,
                    )
                    agent = Agent(
                        public_id=agent_public_id,
                        workspace_id=workspace_id,
                        name="Retrieval agent",
                        default_locale="vi",
                        created_by_user_id=user_id,
                    )
                    session.add_all([knowledge_base, agent])
                    await session.flush()
                    session.add(
                        AgentKnowledgeBase(
                            workspace_id=workspace_id,
                            agent_id=agent.id,
                            knowledge_base_id=knowledge_base.id,
                        )
                    )
                    document = KnowledgeDocument(
                        workspace_id=workspace_id,
                        knowledge_base_id=knowledge_base.id,
                        title="Return policy",
                        kind="policy",
                    )
                    session.add(document)
                    await session.flush()
                    version = KnowledgeDocumentVersion(
                        workspace_id=workspace_id,
                        document_id=document.id,
                        version_no=1,
                        source_kind="manual",
                        source_text="Returns within seven days.",
                        content_sha256="a" * 64,
                        mime_type="text/plain",
                        byte_size=26,
                        created_by_user_id=user_id,
                    )
                    session.add(version)
                    await session.flush()
                    generation = KnowledgeGeneration(
                        workspace_id=workspace_id,
                        document_id=document.id,
                        document_version_id=version.id,
                        embedding_profile_id=profile.id,
                        generation_no=1,
                        status="ready",
                        chunker_version="test-v1",
                        chunk_size=100,
                        chunk_overlap=10,
                        pipeline_config_hash="b" * 64,
                    )
                    session.add(generation)
                    await session.flush()
                    chunk = KnowledgeChunk(
                        workspace_id=workspace_id,
                        generation_id=generation.id,
                        position=0,
                        content="Returns within seven days.",
                        content_sha256="c" * 64,
                        source_locator=f"document:{document.id}:version:1:chars:0-26",
                        metadata_json={},
                    )
                    session.add(chunk)
                    await session.flush()
                    session.add_all(
                        [
                            KnowledgeChunkEmbedding(
                                workspace_id=workspace_id,
                                chunk_id=chunk.id,
                                embedding_profile_id=profile.id,
                                qdrant_point_id=point_id,
                                content_hash=chunk.content_sha256,
                                status="indexed",
                            ),
                            KnowledgeDocumentActiveGeneration(
                                workspace_id=workspace_id,
                                document_id=document.id,
                                generation_id=generation.id,
                            ),
                        ]
                    )
                    await session.flush()
                    hit = VectorSearchHit(
                        point_id=point_id,
                        score=0.9,
                        payload={
                            "workspace_id": str(workspace_id),
                            "knowledge_base_id": knowledge_base.id,
                            "document_id": document.id,
                            "document_version_id": version.id,
                            "generation_id": generation.id,
                            "generation": generation.generation_no,
                            "chunk_id": chunk.id,
                            "embedding_profile_id": profile.id,
                            "content_hash": chunk.content_sha256,
                        },
                    )
                    scope = await resolve_agent_knowledge_scope(
                        session,
                        workspace_id=workspace_id,
                        public_agent_id=agent_public_id,
                    )
                    retrieval = KnowledgeRetrievalService(
                        session,
                        embedding_provider=FakeEmbeddingProvider(),
                        vector_index=FakeVectorIndex(hit),
                    )
                    results = await retrieval.search(scope, "return policy")
                    assert [result.content for result in results] == [
                        "Returns within seven days."
                    ]

                    generation.status = "revoked"
                    await session.flush()
                    assert await retrieval.search(scope, "return policy") == []
                finally:
                    await session.close()
                    await transaction.rollback()
        finally:
            await engine.dispose()

    try:
        asyncio.run(exercise())
    finally:
        reset_test_schema(database_url, create=False)
