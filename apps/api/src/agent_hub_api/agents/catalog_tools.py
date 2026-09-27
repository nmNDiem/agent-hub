from typing import cast

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.tool_schemas import (
    CatalogToolAvailability,
    CatalogToolAvailabilitySummary,
    CatalogToolImageReference,
    CatalogToolPriceSummary,
    CatalogToolProduct,
    CatalogToolSizeGuide,
    CatalogToolVariant,
    CheckStockToolInput,
    CheckStockToolResult,
    GetProductDetailToolInput,
    SearchProductsToolInput,
    SearchProductsToolResult,
)
from agent_hub_api.catalog.read_models import (
    AuthorizedCatalogScope,
    CatalogAvailability,
    CatalogProductReadModel,
    CatalogQuery,
)
from agent_hub_api.catalog.read_service import CatalogReadService


class AgentCatalogTools:
    """Typed read-only catalog tools bound to one immutable authorized scope."""

    def __init__(self, session: AsyncSession, scope: AuthorizedCatalogScope) -> None:
        self.catalog = CatalogReadService(session)
        self.scope = scope

    async def search_products(
        self, payload: SearchProductsToolInput
    ) -> SearchProductsToolResult:
        products = await self.catalog.search_products(
            self.scope,
            CatalogQuery(
                text=payload.query,
                brand=payload.brand,
                price_min=payload.min_price,
                price_max=payload.max_price,
                in_stock=payload.in_stock,
                options=tuple(f"{name}:{value}" for name, value in payload.options.items()),
                attributes=tuple(
                    f"{name}:{value}" for name, value in payload.attributes.items()
                ),
                requested_location_ids=self._ids(payload.location_ids),
                requested_collection_ids=self._ids(payload.collection_ids),
                limit=payload.limit,
            ),
        )
        return SearchProductsToolResult(items=[self._product(item) for item in products])

    async def get_product_detail(
        self, payload: GetProductDetailToolInput
    ) -> CatalogToolProduct | None:
        product = await self.catalog.get_product_detail(
            self.scope,
            payload.product_id,
            location_ids=self._ids(payload.location_ids),
            collection_ids=self._ids(payload.collection_ids),
        )
        return self._product(product) if product is not None else None

    async def check_stock(self, payload: CheckStockToolInput) -> CheckStockToolResult | None:
        item = await self.catalog.get_variant_availability(
            self.scope,
            payload.variant_id,
            location_ids=self._ids(payload.location_ids),
        )
        if item is None:
            return None
        return CheckStockToolResult(
            variant_id=item.id,
            sku=item.sku,
            inventory_policy=item.inventory_policy,
            availability=[self._availability(value) for value in item.availability],
        )

    @staticmethod
    def _ids(values: list[int] | None) -> frozenset[int] | None:
        return frozenset(values) if values is not None else None

    @staticmethod
    def _availability(item: CatalogAvailability) -> CatalogToolAvailability:
        return CatalogToolAvailability(
            location_id=item.location_id,
            location_name=item.location_name,
            location_code=item.location_code,
            quantity=item.quantity,
            inventory_state=item.inventory_state,
            inventory_updated_at=item.inventory_updated_at,
            effective_price=item.effective_price,
        )

    @classmethod
    def _product(cls, product: CatalogProductReadModel) -> CatalogToolProduct:
        guide = (
            CatalogToolSizeGuide(
                title=product.size_guide.title,
                content=cast(dict[str, JsonValue], dict(product.size_guide.content)),
                updated_at=product.size_guide.updated_at,
            )
            if product.size_guide is not None
            else None
        )
        return CatalogToolProduct(
            id=product.id,
            sku=product.sku,
            name=product.name,
            description=product.description,
            brand=product.brand,
            category=product.category,
            currency=product.currency,
            base_price=product.base_price,
            product_url=product.product_url,
            attributes=cast(dict[str, JsonValue], dict(product.attributes)),
            price=CatalogToolPriceSummary(
                kind=product.price.kind,
                minimum=product.price.minimum,
                maximum=product.price.maximum,
            ),
            availability=CatalogToolAvailabilitySummary(
                total_locations=product.availability.total_locations,
                in_stock_locations=product.availability.in_stock_locations,
                out_of_stock_locations=product.availability.out_of_stock_locations,
                unknown_locations=product.availability.unknown_locations,
            ),
            variants=[
                CatalogToolVariant(
                    id=variant.id,
                    sku=variant.sku,
                    name=variant.name,
                    inventory_policy=variant.inventory_policy,
                    options=dict(variant.options),
                    attributes=cast(dict[str, JsonValue], dict(variant.attributes)),
                    color=variant.legacy_color,
                    size=variant.legacy_size,
                    availability=[cls._availability(item) for item in variant.availability],
                )
                for variant in product.variants
            ],
            images=[
                CatalogToolImageReference(
                    image_id=image.id,
                    variant_id=image.variant_id,
                    kind=image.kind,
                    alt_text=image.alt_text,
                    sort_order=image.sort_order,
                )
                for image in product.images
            ],
            size_guide=guide,
            updated_at=product.updated_at,
        )
