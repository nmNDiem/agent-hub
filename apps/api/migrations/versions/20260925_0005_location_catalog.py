"""Add workspace locations, location inventory/pricing, and catalog collections.

Revision ID: 20260925_0005
Revises: 20260925_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0005"
down_revision: str | None = "20260925_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("code", sa.String(80), nullable=True),
        sa.Column("type", sa.String(24), server_default="store", nullable=False),
        sa.Column("address_json", JSONB, server_default="{}", nullable=False),
        sa.Column("metadata_json", JSONB, server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_locations_name_nonempty"),
        sa.CheckConstraint(
            "type IN ('store','warehouse','showroom','service','online','other')",
            name="ck_locations_type",
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_locations_workspace_id_id"),
        sa.UniqueConstraint("workspace_id", "code", name="uq_locations_workspace_code"),
    )
    op.create_index("ix_locations_workspace_id", "locations", ["workspace_id"])
    op.create_index(
        "ix_locations_workspace_active", "locations", ["workspace_id", "is_active", "created_at"]
    )

    op.create_table(
        "location_variants",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("location_id", sa.BigInteger(), primary_key=True),
        sa.Column("variant_id", sa.BigInteger(), primary_key=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("price_override", sa.Numeric(18, 2), nullable=True),
        sa.Column("compare_at_price_override", sa.Numeric(18, 2), nullable=True),
        sa.Column("metadata_json", JSONB, server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "location_id"],
            ["locations.workspace_id", "locations.id"],
            name="fk_location_variants_workspace_location",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "variant_id"],
            ["product_variants.workspace_id", "product_variants.id"],
            name="fk_location_variants_workspace_variant",
        ),
        sa.CheckConstraint(
            "price_override IS NULL OR price_override >= 0",
            name="ck_location_variants_price_nonnegative",
        ),
        sa.CheckConstraint(
            "compare_at_price_override IS NULL OR compare_at_price_override >= 0",
            name="ck_location_variants_compare_price_nonnegative",
        ),
    )
    op.create_index(
        "ix_location_variants_workspace_variant",
        "location_variants",
        ["workspace_id", "variant_id"],
    )

    op.create_table(
        "inventory_levels",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("location_id", sa.BigInteger(), primary_key=True),
        sa.Column("variant_id", sa.BigInteger(), primary_key=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "location_id"],
            ["locations.workspace_id", "locations.id"],
            name="fk_inventory_levels_workspace_location",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "variant_id"],
            ["product_variants.workspace_id", "product_variants.id"],
            name="fk_inventory_levels_workspace_variant",
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity >= 0", name="ck_inventory_quantity_nonnegative"
        ),
    )
    op.create_index(
        "ix_inventory_levels_workspace_variant",
        "inventory_levels",
        ["workspace_id", "variant_id"],
    )

    op.create_table(
        "catalog_collections",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_catalog_collections_name_nonempty"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_catalog_collections_workspace_id_id"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_catalog_collections_workspace_name"),
    )
    op.create_index("ix_catalog_collections_workspace_id", "catalog_collections", ["workspace_id"])
    op.create_index(
        "ix_catalog_collections_workspace_active",
        "catalog_collections",
        ["workspace_id", "is_active"],
    )

    op.create_table(
        "catalog_collection_products",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("collection_id", sa.BigInteger(), primary_key=True),
        sa.Column("product_id", sa.BigInteger(), primary_key=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "collection_id"],
            ["catalog_collections.workspace_id", "catalog_collections.id"],
            name="fk_collection_products_workspace_collection",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "product_id"],
            ["products.workspace_id", "products.id"],
            name="fk_collection_products_workspace_product",
        ),
    )
    op.create_index(
        "ix_collection_products_workspace_product",
        "catalog_collection_products",
        ["workspace_id", "product_id"],
    )

    # Every existing catalog receives one explicit migration target. Product-only
    # records receive a generic variant so inventory remains variant-scoped.
    op.execute("""
        INSERT INTO locations (workspace_id, name, code, type, metadata_json)
        SELECT DISTINCT workspace_id, 'Default location', 'DEFAULT', 'store',
               '{"system_default": true}'::jsonb
        FROM products
    """)
    op.execute("""
        INSERT INTO product_variants (
            workspace_id, product_id, variant_sku, name, price_override,
            stock_quantity, inventory_policy, attributes_json, status
        )
        SELECT p.workspace_id, p.id, NULL, NULL, NULL,
               p.stock_quantity, p.inventory_policy, '{"system_default": true}'::jsonb, p.status
        FROM products p
        WHERE NOT EXISTS (
            SELECT 1 FROM product_variants v
            WHERE v.workspace_id = p.workspace_id AND v.product_id = p.id
        )
    """)
    op.execute("""
        INSERT INTO location_variants (workspace_id, location_id, variant_id, is_active)
        SELECT v.workspace_id, l.id, v.id, (v.status = 'active')
        FROM product_variants v
        JOIN locations l ON l.workspace_id = v.workspace_id AND l.code = 'DEFAULT'
    """)
    op.execute("""
        INSERT INTO inventory_levels (workspace_id, location_id, variant_id, quantity)
        SELECT v.workspace_id, l.id, v.id, v.stock_quantity
        FROM product_variants v
        JOIN locations l ON l.workspace_id = v.workspace_id AND l.code = 'DEFAULT'
    """)

    op.drop_constraint("ck_products_stock_nonnegative", "products", type_="check")
    op.drop_column("products", "stock_quantity")
    op.drop_constraint("ck_product_variants_stock_nonnegative", "product_variants", type_="check")
    op.drop_column("product_variants", "stock_quantity")


def downgrade() -> None:
    op.add_column("products", sa.Column("stock_quantity", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_products_stock_nonnegative", "products", "stock_quantity IS NULL OR stock_quantity >= 0"
    )
    op.add_column("product_variants", sa.Column("stock_quantity", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_product_variants_stock_nonnegative",
        "product_variants",
        "stock_quantity IS NULL OR stock_quantity >= 0",
    )
    op.execute("""
        UPDATE product_variants v
        SET stock_quantity = i.quantity
        FROM inventory_levels i
        JOIN locations l
          ON l.workspace_id = i.workspace_id AND l.id = i.location_id AND l.code = 'DEFAULT'
        WHERE v.workspace_id = i.workspace_id AND v.id = i.variant_id
    """)
    op.execute("""
        UPDATE products p
        SET stock_quantity = i.quantity
        FROM product_variants v
        JOIN inventory_levels i
          ON i.workspace_id = v.workspace_id AND i.variant_id = v.id
        JOIN locations l
          ON l.workspace_id = i.workspace_id AND l.id = i.location_id AND l.code = 'DEFAULT'
        WHERE p.workspace_id = v.workspace_id
          AND p.id = v.product_id
          AND v.attributes_json ->> 'system_default' = 'true'
    """)

    op.drop_table("catalog_collection_products")
    op.drop_table("catalog_collections")
    op.drop_table("inventory_levels")
    op.drop_table("location_variants")
    op.drop_table("locations")
