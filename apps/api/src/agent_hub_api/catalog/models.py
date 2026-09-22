from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agent_hub_api.core.database import BIGINT_PRIMARY_KEY, Base, utc_now


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
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
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
        CheckConstraint(
            "stock_quantity IS NULL OR stock_quantity >= 0",
            name="ck_product_variants_stock_nonnegative",
        ),
        Index("ix_product_variants_workspace_product", "workspace_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    product_id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY)
    variant_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    size: Mapped[str | None] = mapped_column(String(80), nullable=True)
    price_override: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    stock_quantity: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


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
    object_key: Mapped[str] = mapped_column(String(1024))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer())
    width: Mapped[int] = mapped_column(Integer())
    height: Mapped[int] = mapped_column(Integer())
    sha256: Mapped[str] = mapped_column(String(64))
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
        CheckConstraint(
            "status IN ('processing', 'completed', 'failed')", name="ck_catalog_imports_status"
        ),
        Index("ix_catalog_imports_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="processing")
    result: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
