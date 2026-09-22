"""Add F2 workspace-scoped catalog and import state.

Revision ID: 20260922_0003
Revises: 20260921_0002
Create Date: 2026-09-22 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0003"
down_revision: str | None = "20260921_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("product_sku", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="VND", nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("product_url", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("price IS NULL OR price >= 0", name="ck_products_price_nonnegative"),
        sa.CheckConstraint(
            "product_sku IS NULL OR (product_sku = upper(product_sku) AND length(product_sku) > 0)",
            name="ck_products_sku_normalized",
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_products_status"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_products_workspace_id_id"),
        sa.UniqueConstraint("workspace_id", "product_sku", name="uq_products_workspace_sku"),
    )
    op.create_index("ix_products_workspace_id", "products", ["workspace_id"])
    op.create_index("ix_products_workspace_category", "products", ["workspace_id", "category"])
    op.create_index(
        "ix_products_workspace_status_created",
        "products",
        ["workspace_id", "status", "created_at", "id"],
    )

    op.create_table(
        "product_variants",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_sku", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("color", sa.String(length=80), nullable=True),
        sa.Column("size", sa.String(length=80), nullable=True),
        sa.Column("price_override", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("stock_quantity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "price_override IS NULL OR price_override >= 0",
            name="ck_product_variants_price_nonnegative",
        ),
        sa.CheckConstraint(
            "stock_quantity IS NULL OR stock_quantity >= 0",
            name="ck_product_variants_stock_nonnegative",
        ),
        sa.CheckConstraint(
            "variant_sku IS NULL OR (variant_sku = upper(variant_sku) AND length(variant_sku) > 0)",
            name="ck_product_variants_sku_normalized",
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_product_variants_status"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_product_variants_workspace_product",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_product_variants_workspace_id_id"),
        sa.UniqueConstraint(
            "workspace_id", "variant_sku", name="uq_product_variants_workspace_sku"
        ),
    )
    op.create_index("ix_product_variants_workspace_id", "product_variants", ["workspace_id"])
    op.create_index(
        "ix_product_variants_workspace_product",
        "product_variants",
        ["workspace_id", "product_id"],
    )

    op.create_table(
        "size_guides",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_size_guides_workspace_product",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_size_guides_workspace_id_id"),
        sa.UniqueConstraint("workspace_id", "product_id", name="uq_size_guides_workspace_product"),
    )
    op.create_index("ix_size_guides_workspace_id", "size_guides", ["workspace_id"])

    op.create_table(
        "product_images",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=True),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("alt_text", sa.String(length=300), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="uploading", nullable=False),
        sa.Column("cleanup_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_cleanup_error", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('uploading', 'active', 'cleanup_pending', 'deleted')",
            name="ck_product_images_status",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_product_images_workspace_product",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "variant_id"],
            ["product_variants.workspace_id", "product_variants.id"],
            name="fk_product_images_workspace_variant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_product_images_object_key"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_product_images_workspace_id_id"),
    )
    op.create_index("ix_product_images_workspace_id", "product_images", ["workspace_id"])
    op.create_index(
        "ix_product_images_workspace_product",
        "product_images",
        ["workspace_id", "product_id", "sort_order"],
    )

    op.create_table(
        "catalog_imports",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="processing", nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'completed', 'failed')", name="ck_catalog_imports_status"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_catalog_imports_workspace_key"
        ),
    )
    op.create_index("ix_catalog_imports_workspace_id", "catalog_imports", ["workspace_id"])
    op.create_index(
        "ix_catalog_imports_workspace_created", "catalog_imports", ["workspace_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_imports_workspace_created", table_name="catalog_imports")
    op.drop_index("ix_catalog_imports_workspace_id", table_name="catalog_imports")
    op.drop_table("catalog_imports")
    op.drop_index("ix_product_images_workspace_product", table_name="product_images")
    op.drop_index("ix_product_images_workspace_id", table_name="product_images")
    op.drop_table("product_images")
    op.drop_index("ix_size_guides_workspace_id", table_name="size_guides")
    op.drop_table("size_guides")
    op.drop_index("ix_product_variants_workspace_product", table_name="product_variants")
    op.drop_index("ix_product_variants_workspace_id", table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_index("ix_products_workspace_status_created", table_name="products")
    op.drop_index("ix_products_workspace_category", table_name="products")
    op.drop_index("ix_products_workspace_id", table_name="products")
    op.drop_table("products")
