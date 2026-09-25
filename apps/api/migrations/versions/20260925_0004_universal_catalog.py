"""Add the generic catalog and universal import pipeline.

Revision ID: 20260925_0004
Revises: 20260922_0003
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260925_0004"
down_revision: str | None = "20260922_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    for name, type_, nullable, default in (
        ("barcode", sa.String(100), True, None),
        ("slug", sa.String(220), True, None),
        ("brand", sa.String(160), True, None),
        ("description_html_source", sa.Text(), True, None),
        ("description_html_sanitized", sa.Text(), True, None),
        ("description_text", sa.Text(), True, None),
        ("compare_at_price", sa.Numeric(18, 2), True, None),
        ("stock_quantity", sa.Integer(), True, None),
        ("inventory_policy", sa.String(16), False, "unknown"),
        ("attributes_json", JSONB, False, "{}"),
    ):
        op.add_column("products", sa.Column(name, type_, nullable=nullable, server_default=default))
    op.create_check_constraint(
        "ck_products_inventory_policy",
        "products",
        "inventory_policy IN ('tracked','untracked','unknown')",
    )
    op.create_check_constraint(
        "ck_products_stock_nonnegative", "products", "stock_quantity IS NULL OR stock_quantity >= 0"
    )
    op.create_check_constraint(
        "ck_products_compare_price_nonnegative",
        "products",
        "compare_at_price IS NULL OR compare_at_price >= 0",
    )

    for name, type_, nullable, default in (
        ("barcode", sa.String(100), True, None),
        ("compare_at_price", sa.Numeric(18, 2), True, None),
        ("inventory_policy", sa.String(16), False, "unknown"),
        ("option_signature", sa.String(512), True, None),
        ("attributes_json", JSONB, False, "{}"),
    ):
        op.add_column(
            "product_variants", sa.Column(name, type_, nullable=nullable, server_default=default)
        )
    op.create_check_constraint(
        "ck_variants_inventory_policy",
        "product_variants",
        "inventory_policy IN ('tracked','untracked','unknown')",
    )
    op.create_check_constraint(
        "ck_variants_compare_price_nonnegative",
        "product_variants",
        "compare_at_price IS NULL OR compare_at_price >= 0",
    )

    op.alter_column("product_images", "object_key", existing_type=sa.String(1024), nullable=True)
    for column, type_ in (
        ("original_filename", sa.String(255)),
        ("content_type", sa.String(64)),
        ("byte_size", sa.Integer()),
        ("width", sa.Integer()),
        ("height", sa.Integer()),
        ("sha256", sa.String(64)),
    ):
        op.alter_column("product_images", column, existing_type=type_, nullable=True)
    op.add_column("product_images", sa.Column("source_url", sa.String(2048), nullable=True))
    op.create_check_constraint(
        "ck_product_images_has_source",
        "product_images",
        "object_key IS NOT NULL OR source_url IS NOT NULL",
    )

    op.create_table(
        "product_option_definitions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "product_id"], ["products.workspace_id", "products.id"]
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_option_def_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id", "product_id", "normalized_name", name="uq_option_def_product_name"
        ),
    )
    op.create_index(
        "ix_product_option_definitions_workspace_id", "product_option_definitions", ["workspace_id"]
    )
    op.create_table(
        "product_option_values",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("option_definition_id", sa.BigInteger(), nullable=False),
        sa.Column("value", sa.String(160), nullable=False),
        sa.Column("normalized_value", sa.String(160), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "option_definition_id"],
            ["product_option_definitions.workspace_id", "product_option_definitions.id"],
        ),
        sa.UniqueConstraint("workspace_id", "id", name="uq_option_value_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "option_definition_id",
            "normalized_value",
            name="uq_option_value_definition_value",
        ),
    )
    op.create_index(
        "ix_product_option_values_workspace_id", "product_option_values", ["workspace_id"]
    )
    op.create_table(
        "variant_option_values",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("variant_id", sa.BigInteger(), primary_key=True),
        sa.Column("option_value_id", sa.BigInteger(), primary_key=True),
        sa.Column("option_definition_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "variant_id"], ["product_variants.workspace_id", "product_variants.id"]
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "option_value_id"],
            ["product_option_values.workspace_id", "product_option_values.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "option_definition_id"],
            ["product_option_definitions.workspace_id", "product_option_definitions.id"],
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "variant_id",
            "option_definition_id",
            name="uq_variant_option_definition",
        ),
    )

    op.execute("""
        INSERT INTO product_option_definitions (workspace_id, product_id, name, normalized_name, position)
        SELECT workspace_id, product_id, 'Color', 'color', 0 FROM product_variants WHERE color IS NOT NULL GROUP BY workspace_id, product_id
        UNION ALL
        SELECT workspace_id, product_id, 'Size', 'size', 1 FROM product_variants WHERE size IS NOT NULL GROUP BY workspace_id, product_id
    """)
    op.execute("""
        INSERT INTO product_option_values (workspace_id, option_definition_id, value, normalized_value, position)
        SELECT d.workspace_id, d.id, v.color, lower(trim(v.color)), 0 FROM product_variants v JOIN product_option_definitions d ON d.workspace_id=v.workspace_id AND d.product_id=v.product_id AND d.normalized_name='color' WHERE v.color IS NOT NULL GROUP BY d.workspace_id,d.id,v.color
        UNION ALL
        SELECT d.workspace_id, d.id, v.size, lower(trim(v.size)), 0 FROM product_variants v JOIN product_option_definitions d ON d.workspace_id=v.workspace_id AND d.product_id=v.product_id AND d.normalized_name='size' WHERE v.size IS NOT NULL GROUP BY d.workspace_id,d.id,v.size
    """)
    op.execute("""
        INSERT INTO variant_option_values (workspace_id, variant_id, option_value_id, option_definition_id)
        SELECT v.workspace_id,v.id,ov.id,d.id FROM product_variants v JOIN product_option_definitions d ON d.workspace_id=v.workspace_id AND d.product_id=v.product_id JOIN product_option_values ov ON ov.workspace_id=d.workspace_id AND ov.option_definition_id=d.id AND ov.normalized_value=lower(trim(CASE d.normalized_name WHEN 'color' THEN v.color ELSE v.size END)) WHERE CASE d.normalized_name WHEN 'color' THEN v.color ELSE v.size END IS NOT NULL
    """)

    op.create_table(
        "catalog_external_refs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("namespace", sa.String(120), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "namespace",
            "entity_type",
            "external_id",
            name="uq_catalog_external_ref",
        ),
    )
    op.create_index(
        "ix_catalog_external_refs_lookup",
        "catalog_external_refs",
        ["workspace_id", "namespace", "external_id"],
    )

    op.drop_constraint("ck_catalog_imports_status", "catalog_imports", type_="check")
    op.alter_column(
        "catalog_imports", "idempotency_key", existing_type=sa.String(128), nullable=True
    )
    op.alter_column(
        "catalog_imports",
        "lease_expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column(
        "catalog_imports",
        "status",
        existing_type=sa.String(16),
        type_=sa.String(24),
        nullable=False,
    )
    for name, type_ in (
        ("original_filename", sa.String(255)),
        ("file_type", sa.String(8)),
        ("schema_fingerprint", sa.String(64)),
    ):
        op.add_column("catalog_imports", sa.Column(name, type_, nullable=True))
    op.add_column(
        "catalog_imports", sa.Column("mapping_profile_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "catalog_imports",
        sa.Column("catalog_revision_at_analysis", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "catalog_imports", sa.Column("summary_json", JSONB, server_default="{}", nullable=False)
    )
    op.add_column(
        "catalog_imports", sa.Column("metadata_json", JSONB, server_default="{}", nullable=False)
    )
    op.add_column("catalog_imports", sa.Column("source_content", sa.LargeBinary(), nullable=True))
    op.add_column(
        "catalog_imports",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.add_column(
        "catalog_imports", sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_catalog_imports_status_v2",
        "catalog_imports",
        "status IN ('uploaded','analyzing','needs_confirmation','ready','committing','committed','failed','processing','completed')",
    )

    op.create_table(
        "catalog_import_mapping_profiles",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("schema_fingerprint", sa.String(64), nullable=False),
        sa.Column("mapping_json", JSONB, nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("confirmed_by_user", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_mapping_profiles_workspace_fingerprint",
        "catalog_import_mapping_profiles",
        ["workspace_id", "schema_fingerprint"],
    )
    op.create_table(
        "catalog_import_staged_records",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column(
            "import_id", sa.BigInteger(), sa.ForeignKey("catalog_imports.id"), nullable=False
        ),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("source_location", JSONB, nullable=False),
        sa.Column("normalized_json", JSONB, nullable=False),
        sa.Column("identity_json", JSONB, server_default="{}", nullable=False),
        sa.Column("mutation", sa.String(16), nullable=False),
        sa.Column("target_entity_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_staged_records_import", "catalog_import_staged_records", ["workspace_id", "import_id"]
    )
    op.create_table(
        "catalog_import_issues",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column(
            "import_id", sa.BigInteger(), sa.ForeignKey("catalog_imports.id"), nullable=False
        ),
        sa.Column("issue_type", sa.String(48), nullable=False),
        sa.Column("severity", sa.String(24), nullable=False),
        sa.Column("entity_scope", sa.String(24), nullable=True),
        sa.Column("source_location", JSONB, server_default="{}", nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence_json", JSONB, server_default="{}", nullable=False),
        sa.Column("options_json", JSONB, server_default="[]", nullable=False),
        sa.Column("status", sa.String(16), server_default="open", nullable=False),
        sa.Column("resolution_json", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_import_issues_status", "catalog_import_issues", ["workspace_id", "import_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("catalog_import_issues")
    op.drop_table("catalog_import_staged_records")
    op.drop_table("catalog_import_mapping_profiles")
    op.drop_constraint("ck_catalog_imports_status_v2", "catalog_imports", type_="check")
    for name in (
        "committed_at",
        "updated_at",
        "source_content",
        "metadata_json",
        "summary_json",
        "catalog_revision_at_analysis",
        "mapping_profile_id",
        "schema_fingerprint",
        "file_type",
        "original_filename",
    ):
        op.drop_column("catalog_imports", name)
    op.alter_column(
        "catalog_imports", "idempotency_key", existing_type=sa.String(128), nullable=False
    )
    op.alter_column(
        "catalog_imports",
        "lease_expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "catalog_imports",
        "status",
        existing_type=sa.String(24),
        type_=sa.String(16),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_catalog_imports_status",
        "catalog_imports",
        "status IN ('processing','completed','failed')",
    )
    op.drop_table("catalog_external_refs")
    op.drop_table("variant_option_values")
    op.drop_table("product_option_values")
    op.drop_table("product_option_definitions")
    op.drop_constraint("ck_product_images_has_source", "product_images", type_="check")
    op.drop_column("product_images", "source_url")
    for table, columns in (
        (
            "product_variants",
            (
                "attributes_json",
                "option_signature",
                "inventory_policy",
                "compare_at_price",
                "barcode",
            ),
        ),
        (
            "products",
            (
                "attributes_json",
                "inventory_policy",
                "stock_quantity",
                "compare_at_price",
                "description_text",
                "description_html_sanitized",
                "description_html_source",
                "brand",
                "slug",
                "barcode",
            ),
        ),
    ):
        for column in columns:
            op.drop_column(table, column)
