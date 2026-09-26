from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_products_workspace_id_id"),
        UniqueConstraint("workspace_id", "product_sku", name="uq_products_workspace_sku"),
        CheckConstraint(
            "product_sku IS NULL OR (product_sku = upper(product_sku) AND length(product_sku) > 0)",
            name="ck_products_sku_normalized",
        ),
        CheckConstraint("status IN ('active', 'archived')", name="ck_products_status"),
        CheckConstraint("price IS NULL OR price >= 0", name="ck_products_price_nonnegative"),
        Index("ix_products_workspace_status_created", "workspace_id", "status", "created_at", "id"),
        Index("ix_products_workspace_category", "workspace_id", "category"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    product_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str | None] = mapped_column(String(220), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    description_html_source: Mapped[str | None] = mapped_column(Text(), nullable=True)
    description_html_sanitized: Mapped[str | None] = mapped_column(Text(), nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    inventory_policy: Mapped[str] = mapped_column(String(16), default="unknown")
    attributes_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    product_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_product_variants_workspace_id_id"),
        UniqueConstraint("workspace_id", "variant_sku", name="uq_product_variants_workspace_sku"),
        CheckConstraint(
            "variant_sku IS NULL OR (variant_sku = upper(variant_sku) AND length(variant_sku) > 0)",
            name="ck_product_variants_sku_normalized",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_product_variants_workspace_product",
        ),
        CheckConstraint("status IN ('active', 'archived')", name="ck_product_variants_status"),
        CheckConstraint(
            "price_override IS NULL OR price_override >= 0",
            name="ck_product_variants_price_nonnegative",
        ),
        Index("ix_product_variants_workspace_product", "workspace_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    product_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    variant_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size: Mapped[str | None] = mapped_column(String(80), nullable=True)
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    inventory_policy: Mapped[str] = mapped_column(String(16), default="unknown")
    option_signature: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attributes_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_locations_workspace_id_id"),
        UniqueConstraint("workspace_id", "code", name="uq_locations_workspace_code"),
        CheckConstraint("length(trim(name)) > 0", name="ck_locations_name_nonempty"),
        CheckConstraint(
            "type IN ('store','warehouse','showroom','service','online','other')",
            name="ck_locations_type",
        ),
        Index("ix_locations_workspace_active", "workspace_id", "is_active", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    type: Mapped[str] = mapped_column(String(24), default="store")
    address_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class LocationVariant(Base):
    __tablename__ = "location_variants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "location_id"],
            ["locations.workspace_id", "locations.id"],
            name="fk_location_variants_workspace_location",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "variant_id"],
            ["product_variants.workspace_id", "product_variants.id"],
            name="fk_location_variants_workspace_variant",
        ),
        CheckConstraint(
            "price_override IS NULL OR price_override >= 0",
            name="ck_location_variants_price_nonnegative",
        ),
        CheckConstraint(
            "compare_at_price_override IS NULL OR compare_at_price_override >= 0",
            name="ck_location_variants_compare_price_nonnegative",
        ),
        Index("ix_location_variants_workspace_variant", "workspace_id", "variant_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    location_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    variant_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    compare_at_price_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class InventoryLevel(Base):
    __tablename__ = "inventory_levels"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "location_id"],
            ["locations.workspace_id", "locations.id"],
            name="fk_inventory_levels_workspace_location",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "variant_id"],
            ["product_variants.workspace_id", "product_variants.id"],
            name="fk_inventory_levels_workspace_variant",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity >= 0", name="ck_inventory_quantity_nonnegative"
        ),
        Index("ix_inventory_levels_workspace_variant", "workspace_id", "variant_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    location_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    variant_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    quantity: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CatalogCollection(Base):
    __tablename__ = "catalog_collections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_catalog_collections_workspace_id_id"),
        UniqueConstraint("workspace_id", "name", name="uq_catalog_collections_workspace_name"),
        CheckConstraint("length(trim(name)) > 0", name="ck_catalog_collections_name_nonempty"),
        Index("ix_catalog_collections_workspace_active", "workspace_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CatalogCollectionProduct(Base):
    __tablename__ = "catalog_collection_products"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "collection_id"],
            ["catalog_collections.workspace_id", "catalog_collections.id"],
            name="fk_collection_products_workspace_collection",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_collection_products_workspace_product",
        ),
        Index("ix_collection_products_workspace_product", "workspace_id", "product_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    collection_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    product_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)


class SizeGuide(Base):
    __tablename__ = "size_guides"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_size_guides_workspace_id_id"),
        UniqueConstraint("workspace_id", "product_id", name="uq_size_guides_workspace_product"),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_size_guides_workspace_product",
        ),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    product_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    title: Mapped[str] = mapped_column(String(160))
    content: Mapped[dict[str, object]] = mapped_column(JSON())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_product_images_workspace_id_id"),
        UniqueConstraint("object_key", name="uq_product_images_object_key"),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_product_images_workspace_product",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "variant_id"],
            ["product_variants.workspace_id", "product_variants.id"],
            name="fk_product_images_workspace_variant",
        ),
        CheckConstraint(
            "status IN ('uploading', 'active', 'cleanup_pending', 'deleted')",
            name="ck_product_images_status",
        ),
        Index("ix_product_images_workspace_product", "workspace_id", "product_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    product_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    variant_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    height: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)
    status: Mapped[str] = mapped_column(String(24), default="uploading")
    cleanup_attempts: Mapped[int] = mapped_column(Integer(), default=0)
    last_cleanup_error: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CatalogImport(Base):
    __tablename__ = "catalog_imports"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_catalog_imports_workspace_key"
        ),
        Index("ix_catalog_imports_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="uploaded")
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapping_profile_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)
    catalog_revision_at_analysis: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    source_content: Mapped[bytes | None] = mapped_column(LargeBinary(), nullable=True)
    result: Mapped[dict[str, object] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductOptionDefinition(Base):
    __tablename__ = "product_option_definitions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "product_id", "normalized_name", name="uq_option_def_product_name"
        ),
        UniqueConstraint("workspace_id", "id", name="uq_option_def_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "product_id"], ["products.workspace_id", "products.id"]
        ),
    )
    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    product_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    name: Mapped[str] = mapped_column(String(100))
    normalized_name: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer(), default=0)


class ProductOptionValue(Base):
    __tablename__ = "product_option_values"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "option_definition_id",
            "normalized_value",
            name="uq_option_value_definition_value",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_option_value_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "option_definition_id"],
            ["product_option_definitions.workspace_id", "product_option_definitions.id"],
        ),
    )
    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    option_definition_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    value: Mapped[str] = mapped_column(String(160))
    normalized_value: Mapped[str] = mapped_column(String(160))
    position: Mapped[int] = mapped_column(Integer(), default=0)


class VariantOptionValue(Base):
    __tablename__ = "variant_option_values"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "variant_id",
            "option_definition_id",
            name="uq_variant_option_definition",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "variant_id"], ["product_variants.workspace_id", "product_variants.id"]
        ),
        ForeignKeyConstraint(
            ["workspace_id", "option_value_id"],
            ["product_option_values.workspace_id", "product_option_values.id"],
        ),
        ForeignKeyConstraint(
            ["workspace_id", "option_definition_id"],
            ["product_option_definitions.workspace_id", "product_option_definitions.id"],
        ),
    )
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    variant_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    option_value_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True)
    option_definition_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)


class CatalogExternalRef(Base):
    __tablename__ = "catalog_external_refs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "namespace",
            "entity_type",
            "external_id",
            name="uq_catalog_external_ref",
        ),
        Index("ix_catalog_external_refs_lookup", "workspace_id", "namespace", "external_id"),
    )
    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    namespace: Mapped[str] = mapped_column(String(120))
    external_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CatalogImportMappingProfile(Base):
    __tablename__ = "catalog_import_mapping_profiles"
    __table_args__ = (
        Index("ix_mapping_profiles_workspace_fingerprint", "workspace_id", "schema_fingerprint"),
    )
    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    schema_fingerprint: Mapped[str] = mapped_column(String(64))
    mapping_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    confirmed_by_user: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CatalogImportStagedRecord(Base):
    __tablename__ = "catalog_import_staged_records"
    __table_args__ = (Index("ix_staged_records_import", "workspace_id", "import_id"),)
    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("catalog_imports.id"))
    entity_type: Mapped[str] = mapped_column(String(16))
    source_location: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT)
    normalized_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT)
    identity_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    mutation: Mapped[str] = mapped_column(String(16))
    target_entity_id: Mapped[int | None] = mapped_column(BIGINT_PRIMARY_KEY, nullable=True)


class CatalogImportIssue(Base):
    __tablename__ = "catalog_import_issues"
    __table_args__ = (Index("ix_import_issues_status", "workspace_id", "import_id", "status"),)
    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("catalog_imports.id"))
    issue_type: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(24))
    entity_scope: Mapped[str | None] = mapped_column(String(24), nullable=True)
    source_location: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    message: Mapped[str] = mapped_column(Text())
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSON_DOCUMENT, default=dict)
    options_json: Mapped[list[object]] = mapped_column(JSON_DOCUMENT, default=list)
    status: Mapped[str] = mapped_column(String(16), default="open")
    resolution_json: Mapped[dict[str, object] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
