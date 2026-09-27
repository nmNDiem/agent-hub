from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from fastapi import status
from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.catalog.import_pipeline import normalize_label
from agent_hub_api.catalog.models import (
    CatalogCollection,
    CatalogCollectionProduct,
    InventoryLevel,
    Location,
    LocationVariant,
    Product,
    ProductOptionDefinition,
    ProductOptionValue,
    ProductVariant,
    VariantOptionValue,
)
from agent_hub_api.catalog.options import load_variant_options
from agent_hub_api.catalog.read_models import (
    AuthorizedCatalogScope,
    CatalogAvailability,
    CatalogAvailabilitySummary,
    CatalogPriceSummary,
    CatalogProductReadModel,
    CatalogQuery,
    CatalogVariantReadModel,
    InventoryState,
)
from agent_hub_api.core.errors import ApiError


@dataclass(frozen=True)
class _EffectiveScope:
    location_ids: frozenset[int] | None
    collection_ids: frozenset[int] | None


class CatalogReadService:
    """Product-centric catalog reads with authorization independent from dashboard users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_products(
        self, scope: AuthorizedCatalogScope, query: CatalogQuery
    ) -> tuple[CatalogProductReadModel, ...]:
        if query.limit < 1 or query.limit > 100:
            raise ValueError("Catalog query limit must be between 1 and 100")
        effective_scope = await self._resolve_scope(scope, query)
        if self._scope_is_empty(effective_scope):
            return ()

        candidate_stmt = self._join_catalog_rows(select(Product.id, Product.updated_at))
        candidate_stmt = self._apply_scope(candidate_stmt, scope, effective_scope)
        candidate_stmt = self._apply_filters(candidate_stmt, scope, query)
        candidate_stmt = (
            candidate_stmt.distinct()
            .order_by(Product.updated_at.desc(), Product.id.desc())
            .limit(query.limit)
        )
        candidate_ids = [row[0] for row in (await self.session.execute(candidate_stmt)).all()]
        if not candidate_ids:
            return ()
        return await self._hydrate_products(scope, effective_scope, query, candidate_ids)

    async def get_product_detail(
        self,
        scope: AuthorizedCatalogScope,
        product_id: int,
        *,
        location_ids: frozenset[int] | None = None,
        collection_ids: frozenset[int] | None = None,
    ) -> CatalogProductReadModel | None:
        query = CatalogQuery(
            requested_location_ids=location_ids,
            requested_collection_ids=collection_ids,
            limit=1,
        )
        effective_scope = await self._resolve_scope(scope, query)
        if self._scope_is_empty(effective_scope):
            return None
        products = await self._hydrate_products(
            scope,
            effective_scope,
            query,
            [product_id],
            apply_search_filters=False,
        )
        return products[0] if products else None

    async def get_variant_availability(
        self,
        scope: AuthorizedCatalogScope,
        variant_id: int,
        *,
        location_ids: frozenset[int] | None = None,
    ) -> tuple[CatalogAvailability, ...]:
        query = CatalogQuery(requested_location_ids=location_ids)
        effective_scope = await self._resolve_scope(scope, query)
        if self._scope_is_empty(effective_scope):
            return ()
        stmt = self._join_catalog_rows(
            select(Product, ProductVariant, LocationVariant, InventoryLevel, Location)
        )
        stmt = self._apply_scope(stmt, scope, effective_scope).where(
            ProductVariant.id == variant_id
        )
        rows = (await self.session.execute(stmt.order_by(Location.id))).all()
        return tuple(
            self._availability(product, variant, assignment, inventory, location)
            for product, variant, assignment, inventory, location in rows
        )

    async def _resolve_scope(
        self, scope: AuthorizedCatalogScope, query: CatalogQuery
    ) -> _EffectiveScope:
        location_ids = self._narrow_scope(
            scope.allowed_location_ids,
            query.requested_location_ids,
            resource="location",
        )
        collection_ids = self._narrow_scope(
            scope.allowed_collection_ids,
            query.requested_collection_ids,
            resource="collection",
        )
        if location_ids:
            found_locations = frozenset(
                await self.session.scalars(
                    select(Location.id).where(
                        Location.workspace_id == scope.workspace_id,
                        Location.id.in_(location_ids),
                        Location.is_active.is_(True),
                    )
                )
            )
            if found_locations != location_ids:
                self._not_found("location")
        if collection_ids:
            found_collections = frozenset(
                await self.session.scalars(
                    select(CatalogCollection.id).where(
                        CatalogCollection.workspace_id == scope.workspace_id,
                        CatalogCollection.id.in_(collection_ids),
                        CatalogCollection.is_active.is_(True),
                    )
                )
            )
            if found_collections != collection_ids:
                self._not_found("collection")
        return _EffectiveScope(location_ids=location_ids, collection_ids=collection_ids)

    @staticmethod
    def _narrow_scope(
        allowed: frozenset[int] | None,
        requested: frozenset[int] | None,
        *,
        resource: str,
    ) -> frozenset[int] | None:
        if requested is not None and allowed is not None and not requested.issubset(allowed):
            CatalogReadService._not_found(resource)
        return requested if requested is not None else allowed

    @staticmethod
    def _not_found(resource: str) -> None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "NOT_FOUND",
            f"Không tìm thấy {resource}.",
        )

    @staticmethod
    def _scope_is_empty(scope: _EffectiveScope) -> bool:
        return scope.location_ids == frozenset() or scope.collection_ids == frozenset()

    @staticmethod
    def _join_catalog_rows(stmt: Select[Any]) -> Select[Any]:
        return (
            stmt.join(
                ProductVariant,
                and_(
                    ProductVariant.workspace_id == Product.workspace_id,
                    ProductVariant.product_id == Product.id,
                ),
            )
            .join(
                LocationVariant,
                and_(
                    LocationVariant.workspace_id == ProductVariant.workspace_id,
                    LocationVariant.variant_id == ProductVariant.id,
                ),
            )
            .join(
                Location,
                and_(
                    Location.workspace_id == LocationVariant.workspace_id,
                    Location.id == LocationVariant.location_id,
                ),
            )
            .outerjoin(
                InventoryLevel,
                and_(
                    InventoryLevel.workspace_id == LocationVariant.workspace_id,
                    InventoryLevel.location_id == LocationVariant.location_id,
                    InventoryLevel.variant_id == LocationVariant.variant_id,
                ),
            )
            .where(
                Product.status == "active",
                ProductVariant.status == "active",
                LocationVariant.is_active.is_(True),
                Location.is_active.is_(True),
            )
        )

    @staticmethod
    def _apply_scope(
        stmt: Select[Any], scope: AuthorizedCatalogScope, effective: _EffectiveScope
    ) -> Select[Any]:
        stmt = stmt.where(Product.workspace_id == scope.workspace_id)
        if effective.location_ids is not None:
            stmt = stmt.where(LocationVariant.location_id.in_(effective.location_ids))
        if effective.collection_ids is not None:
            stmt = stmt.where(
                exists(
                    select(1).where(
                        CatalogCollectionProduct.workspace_id == scope.workspace_id,
                        CatalogCollectionProduct.collection_id.in_(effective.collection_ids),
                        CatalogCollectionProduct.product_id == Product.id,
                    )
                )
            )
        return stmt

    @staticmethod
    def _apply_filters(
        stmt: Select[Any], scope: AuthorizedCatalogScope, query: CatalogQuery
    ) -> Select[Any]:
        if query.text:
            pattern = f"%{query.text.strip()}%"
            stmt = stmt.where(
                or_(
                    Product.name.ilike(pattern),
                    Product.product_sku.ilike(pattern),
                    ProductVariant.variant_sku.ilike(pattern),
                )
            )
        if query.brand:
            stmt = stmt.where(Product.brand.ilike(query.brand.strip()))
        effective_price = func.coalesce(
            LocationVariant.price_override,
            ProductVariant.price_override,
            Product.price,
        )
        if query.price_min is not None:
            stmt = stmt.where(effective_price >= query.price_min)
        if query.price_max is not None:
            stmt = stmt.where(effective_price <= query.price_max)
        if query.in_stock is True:
            stmt = stmt.where(InventoryLevel.quantity > 0)
        elif query.in_stock is False:
            stmt = stmt.where(InventoryLevel.quantity == 0)

        for name, value in CatalogReadService._parse_filters(
            query.attributes,
            code="INVALID_ATTRIBUTE_FILTER",
            label="Thuộc tính",
        ):
            stmt = stmt.where(
                or_(
                    Product.attributes_json[name].as_string() == value,
                    ProductVariant.attributes_json[name].as_string() == value,
                )
            )
        for name, value in CatalogReadService._parse_filters(
            query.options,
            code="INVALID_OPTION_FILTER",
            label="Option",
            normalize_name=True,
            normalize_value=True,
        ):
            stmt = stmt.where(
                exists(
                    select(1)
                    .select_from(VariantOptionValue)
                    .join(
                        ProductOptionDefinition,
                        and_(
                            ProductOptionDefinition.workspace_id
                            == VariantOptionValue.workspace_id,
                            ProductOptionDefinition.id
                            == VariantOptionValue.option_definition_id,
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
                        VariantOptionValue.workspace_id == scope.workspace_id,
                        VariantOptionValue.variant_id == ProductVariant.id,
                        ProductOptionDefinition.normalized_name == name,
                        ProductOptionValue.normalized_value == value,
                    )
                )
            )
        return stmt

    @staticmethod
    def _parse_filters(
        values: tuple[str, ...],
        *,
        code: str,
        label: str,
        normalize_name: bool = False,
        normalize_value: bool = False,
    ) -> tuple[tuple[str, str], ...]:
        parsed: list[tuple[str, str]] = []
        for raw in values:
            if ":" not in raw:
                raise ApiError(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    code,
                    f"{label} phải có dạng Tên:Giá trị.",
                )
            name, value = (part.strip() for part in raw.split(":", 1))
            if not name or not value:
                raise ApiError(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    code,
                    f"{label} phải có dạng Tên:Giá trị.",
                )
            if normalize_name:
                name = normalize_label(name)
            if normalize_value:
                value = value.casefold()
            parsed.append((name, value))
        return tuple(parsed)

    async def _hydrate_products(
        self,
        scope: AuthorizedCatalogScope,
        effective_scope: _EffectiveScope,
        query: CatalogQuery,
        product_ids: list[int],
        *,
        apply_search_filters: bool = True,
    ) -> tuple[CatalogProductReadModel, ...]:
        stmt = self._join_catalog_rows(
            select(Product, ProductVariant, LocationVariant, InventoryLevel, Location)
        )
        stmt = self._apply_scope(stmt, scope, effective_scope).where(Product.id.in_(product_ids))
        if apply_search_filters:
            stmt = self._apply_filters(stmt, scope, query)
        rows = (
            await self.session.execute(
                stmt.order_by(
                    Product.updated_at.desc(),
                    Product.id.desc(),
                    ProductVariant.id,
                    Location.id,
                )
            )
        ).all()
        variant_ids = list({variant.id for _, variant, _, _, _ in rows})
        option_maps = await load_variant_options(self.session, scope.workspace_id, variant_ids)

        products: dict[int, Product] = {}
        variants: dict[int, ProductVariant] = {}
        product_variant_ids: dict[int, list[int]] = {}
        availability: dict[int, list[CatalogAvailability]] = {}
        for product, variant, assignment, inventory, location in rows:
            products[product.id] = product
            variants[variant.id] = variant
            ids = product_variant_ids.setdefault(product.id, [])
            if variant.id not in ids:
                ids.append(variant.id)
            availability.setdefault(variant.id, []).append(
                self._availability(product, variant, assignment, inventory, location)
            )

        result: list[CatalogProductReadModel] = []
        for product_id in product_ids:
            product = products.get(product_id)
            if product is None:
                continue
            variant_models = tuple(
                CatalogVariantReadModel(
                    id=variants[variant_id].id,
                    sku=variants[variant_id].variant_sku,
                    name=variants[variant_id].name,
                    inventory_policy=variants[variant_id].inventory_policy,
                    options=MappingProxyType(dict(option_maps.get(variant_id, {}))),
                    attributes=MappingProxyType(
                        dict(variants[variant_id].attributes_json or {})
                    ),
                    availability=tuple(availability[variant_id]),
                )
                for variant_id in product_variant_ids[product_id]
            )
            all_availability = tuple(
                item for variant in variant_models for item in variant.availability
            )
            result.append(
                CatalogProductReadModel(
                    id=product.id,
                    sku=product.product_sku,
                    name=product.name,
                    brand=product.brand,
                    category=product.category,
                    currency=product.currency,
                    base_price=product.price,
                    product_url=product.product_url,
                    attributes=MappingProxyType(dict(product.attributes_json or {})),
                    price=self._price_summary(all_availability),
                    availability=self._availability_summary(all_availability),
                    variants=variant_models,
                    updated_at=product.updated_at,
                )
            )
        return tuple(result)

    @staticmethod
    def _availability(
        product: Product,
        variant: ProductVariant,
        assignment: LocationVariant,
        inventory: InventoryLevel | None,
        location: Location,
    ) -> CatalogAvailability:
        quantity = inventory.quantity if inventory is not None else None
        inventory_state: InventoryState
        if quantity is None:
            inventory_state = "unknown"
        elif quantity > 0:
            inventory_state = "in_stock"
        else:
            inventory_state = "out_of_stock"
        effective_price = (
            assignment.price_override
            if assignment.price_override is not None
            else variant.price_override
            if variant.price_override is not None
            else product.price
        )
        return CatalogAvailability(
            location_id=location.id,
            location_name=location.name,
            location_code=location.code,
            quantity=quantity,
            inventory_state=inventory_state,
            inventory_updated_at=inventory.updated_at if inventory is not None else None,
            effective_price=effective_price,
        )

    @staticmethod
    def _price_summary(
        availability: tuple[CatalogAvailability, ...],
    ) -> CatalogPriceSummary:
        prices = sorted(
            {
                item.effective_price
                for item in availability
                if item.effective_price is not None
            }
        )
        if not prices:
            return CatalogPriceSummary(kind="unknown", minimum=None, maximum=None)
        if len(prices) == 1:
            return CatalogPriceSummary(kind="exact", minimum=prices[0], maximum=prices[0])
        return CatalogPriceSummary(kind="range", minimum=prices[0], maximum=prices[-1])

    @staticmethod
    def _availability_summary(
        availability: tuple[CatalogAvailability, ...],
    ) -> CatalogAvailabilitySummary:
        states_by_location: dict[int, list[InventoryState]] = {}
        for item in availability:
            states_by_location.setdefault(item.location_id, []).append(item.inventory_state)
        states: list[InventoryState] = []
        for location_states in states_by_location.values():
            if "in_stock" in location_states:
                states.append("in_stock")
            elif "unknown" in location_states:
                states.append("unknown")
            else:
                states.append("out_of_stock")
        return CatalogAvailabilitySummary(
            total_locations=len(states),
            in_stock_locations=states.count("in_stock"),
            out_of_stock_locations=states.count("out_of_stock"),
            unknown_locations=states.count("unknown"),
        )
