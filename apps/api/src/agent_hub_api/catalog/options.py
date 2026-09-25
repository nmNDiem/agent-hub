from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.catalog.import_pipeline import normalize_label
from agent_hub_api.catalog.models import (
    Product,
    ProductOptionDefinition,
    ProductOptionValue,
    ProductVariant,
    VariantOptionValue,
)


async def set_variant_options(
    session: AsyncSession,
    workspace_id: UUID,
    product: Product,
    variant: ProductVariant,
    options: Mapping[str, str | None],
    *,
    replace_all: bool,
) -> None:
    normalized = {normalize_label(name): (name, value) for name, value in options.items()}
    if replace_all:
        await session.execute(
            delete(VariantOptionValue).where(
                VariantOptionValue.workspace_id == workspace_id,
                VariantOptionValue.variant_id == variant.id,
            )
        )
        variant.color = None
        variant.size = None
    elif normalized:
        definition_ids = select(ProductOptionDefinition.id).where(
            ProductOptionDefinition.workspace_id == workspace_id,
            ProductOptionDefinition.product_id == product.id,
            ProductOptionDefinition.normalized_name.in_(normalized),
        )
        await session.execute(
            delete(VariantOptionValue).where(
                VariantOptionValue.workspace_id == workspace_id,
                VariantOptionValue.variant_id == variant.id,
                VariantOptionValue.option_definition_id.in_(definition_ids),
            )
        )

    signature: list[str] = []
    for position, (normalized_name, (name, value)) in enumerate(normalized.items()):
        if value is None:
            continue
        normalized_value = value.strip().casefold()
        definition = await session.scalar(
            select(ProductOptionDefinition).where(
                ProductOptionDefinition.workspace_id == workspace_id,
                ProductOptionDefinition.product_id == product.id,
                ProductOptionDefinition.normalized_name == normalized_name,
            )
        )
        if definition is None:
            definition = ProductOptionDefinition(
                workspace_id=workspace_id,
                product_id=product.id,
                name=name.strip(),
                normalized_name=normalized_name,
                position=position,
            )
            session.add(definition)
            await session.flush()
        option_value = await session.scalar(
            select(ProductOptionValue).where(
                ProductOptionValue.workspace_id == workspace_id,
                ProductOptionValue.option_definition_id == definition.id,
                ProductOptionValue.normalized_value == normalized_value,
            )
        )
        if option_value is None:
            option_value = ProductOptionValue(
                workspace_id=workspace_id,
                option_definition_id=definition.id,
                value=value.strip(),
                normalized_value=normalized_value,
                position=0,
            )
            session.add(option_value)
            await session.flush()
        session.add(
            VariantOptionValue(
                workspace_id=workspace_id,
                variant_id=variant.id,
                option_value_id=option_value.id,
                option_definition_id=definition.id,
            )
        )
        signature.append(f"{normalized_name}={normalized_value}")
        if normalized_name == "color":
            variant.color = value.strip()
        if normalized_name == "size":
            variant.size = value.strip()
    if replace_all:
        variant.option_signature = "|".join(sorted(signature)) or None


async def load_variant_options(
    session: AsyncSession, workspace_id: UUID, variant_ids: list[int]
) -> dict[int, dict[str, str]]:
    if not variant_ids:
        return {}
    rows = (
        await session.execute(
            select(
                VariantOptionValue.variant_id,
                ProductOptionDefinition.name,
                ProductOptionValue.value,
            )
            .join(
                ProductOptionDefinition,
                and_(
                    ProductOptionDefinition.workspace_id == VariantOptionValue.workspace_id,
                    ProductOptionDefinition.id == VariantOptionValue.option_definition_id,
                ),
            )
            .join(
                ProductOptionValue,
                and_(
                    ProductOptionValue.workspace_id == VariantOptionValue.workspace_id,
                    ProductOptionValue.id == VariantOptionValue.option_value_id,
                ),
            )
            .where(
                VariantOptionValue.workspace_id == workspace_id,
                VariantOptionValue.variant_id.in_(variant_ids),
            )
        )
    ).all()
    result: dict[int, dict[str, str]] = {}
    for variant_id, name, value in rows:
        result.setdefault(variant_id, {})[name] = value
    return result
