from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.catalog.models import (
    CatalogImport,
    Product,
    ProductImage,
    ProductVariant,
    SizeGuide,
)


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_products(
        self,
        *,
        workspace_id: UUID,
        limit: int,
        status: str | None,
        category: str | None,
        query: str | None,
        cursor_created_at: datetime | None,
        cursor_id: int | None,
    ) -> tuple[list[Product], dict[int, int], bool]:
        statement: Select[tuple[Product]] = select(Product).where(
            Product.workspace_id == workspace_id
        )
        if status is not None:
            statement = statement.where(Product.status == status)
        if category is not None:
            statement = statement.where(Product.category == category)
        if query is not None:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(Product.name.ilike(pattern), Product.product_sku.ilike(pattern))
            )
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                or_(
                    Product.created_at < cursor_created_at,
                    and_(Product.created_at == cursor_created_at, Product.id < cursor_id),
                )
            )
        result = await self.session.scalars(
            statement.order_by(Product.created_at.desc(), Product.id.desc()).limit(limit + 1)
        )
        products = list(result.all())
        has_more = len(products) > limit
        page = products[:limit]
        counts: dict[int, int] = {}
        if page:
            count_rows = await self.session.execute(
                select(ProductVariant.product_id, func.count(ProductVariant.id))
                .where(
                    ProductVariant.workspace_id == workspace_id,
                    ProductVariant.product_id.in_([product.id for product in page]),
                    ProductVariant.status == "active",
                )
                .group_by(ProductVariant.product_id)
            )
            counts = {product_id: count for product_id, count in count_rows.all()}
        return page, counts, has_more

    async def get_product(self, workspace_id: UUID, product_id: int) -> Product | None:
        return cast(
            Product | None,
            await self.session.scalar(
                select(Product).where(
                    Product.workspace_id == workspace_id,
                    Product.id == product_id,
                )
            ),
        )

    async def get_product_detail_relations(
        self, workspace_id: UUID, product_id: int
    ) -> tuple[list[ProductVariant], SizeGuide | None, list[ProductImage]]:
        variants = list(
            (
                await self.session.scalars(
                    select(ProductVariant)
                    .where(
                        ProductVariant.workspace_id == workspace_id,
                        ProductVariant.product_id == product_id,
                    )
                    .order_by(ProductVariant.created_at, ProductVariant.id)
                )
            ).all()
        )
        size_guide = await self.session.scalar(
            select(SizeGuide).where(
                SizeGuide.workspace_id == workspace_id,
                SizeGuide.product_id == product_id,
            )
        )
        images = list(
            (
                await self.session.scalars(
                    select(ProductImage)
                    .where(
                        ProductImage.workspace_id == workspace_id,
                        ProductImage.product_id == product_id,
                        ProductImage.status != "deleted",
                    )
                    .order_by(ProductImage.sort_order, ProductImage.id)
                )
            ).all()
        )
        return variants, size_guide, images

    async def get_variant(
        self, workspace_id: UUID, product_id: int, variant_id: int
    ) -> ProductVariant | None:
        return cast(
            ProductVariant | None,
            await self.session.scalar(
                select(ProductVariant).where(
                    ProductVariant.workspace_id == workspace_id,
                    ProductVariant.product_id == product_id,
                    ProductVariant.id == variant_id,
                )
            ),
        )

    async def get_image(
        self, workspace_id: UUID, product_id: int, image_id: int
    ) -> ProductImage | None:
        return cast(
            ProductImage | None,
            await self.session.scalar(
                select(ProductImage).where(
                    ProductImage.workspace_id == workspace_id,
                    ProductImage.product_id == product_id,
                    ProductImage.id == image_id,
                    ProductImage.status != "deleted",
                )
            ),
        )

    async def get_size_guide(self, workspace_id: UUID, product_id: int) -> SizeGuide | None:
        return cast(
            SizeGuide | None,
            await self.session.scalar(
                select(SizeGuide).where(
                    SizeGuide.workspace_id == workspace_id,
                    SizeGuide.product_id == product_id,
                )
            ),
        )

    async def find_product_skus(self, workspace_id: UUID, skus: set[str]) -> set[str]:
        if not skus:
            return set()
        result = await self.session.scalars(
            select(Product.product_sku).where(
                Product.workspace_id == workspace_id,
                Product.product_sku.in_(skus),
            )
        )
        return {sku for sku in result.all() if sku is not None}

    async def find_variant_skus(self, workspace_id: UUID, skus: set[str]) -> set[str]:
        if not skus:
            return set()
        result = await self.session.scalars(
            select(ProductVariant.variant_sku).where(
                ProductVariant.workspace_id == workspace_id,
                ProductVariant.variant_sku.in_(skus),
            )
        )
        return {sku for sku in result.all() if sku is not None}

    async def add_product(self, product: Product) -> None:
        self.session.add(product)
        await self.session.flush()

    async def add_variant(self, variant: ProductVariant) -> None:
        self.session.add(variant)
        await self.session.flush()

    async def add_image(self, image: ProductImage) -> None:
        self.session.add(image)
        await self.session.flush()

    async def delete_size_guide(self, guide: SizeGuide) -> None:
        await self.session.delete(guide)

    async def get_import_by_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> CatalogImport | None:
        return cast(
            CatalogImport | None,
            await self.session.scalar(
                select(CatalogImport).where(
                    CatalogImport.workspace_id == workspace_id,
                    CatalogImport.idempotency_key == idempotency_key,
                )
            ),
        )

    async def reclaim_import(
        self,
        *,
        import_id: int,
        workspace_id: UUID,
        now: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            await self.session.execute(
                update(CatalogImport)
                .where(
                    CatalogImport.id == import_id,
                    CatalogImport.workspace_id == workspace_id,
                    CatalogImport.status == "processing",
                    CatalogImport.lease_expires_at <= now,
                )
                .values(lease_expires_at=lease_expires_at)
            ),
        )
        return bool(result.rowcount)
