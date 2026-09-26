from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from fastapi import status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.catalog.models import (
    CatalogCollection,
    CatalogCollectionProduct,
    InventoryLevel,
    Location,
    LocationVariant,
    Product,
    ProductVariant,
)
from agent_hub_api.catalog.scope_schemas import (
    CollectionCreateRequest,
    CollectionProductResponse,
    CollectionResponse,
    CollectionUpdateRequest,
    LocationCreateRequest,
    LocationResponse,
    LocationUpdateRequest,
    LocationVariantResponse,
    LocationVariantUpdateRequest,
)
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.service import WorkspaceService

DEFAULT_LOCATION_CODE = "DEFAULT"


async def get_or_create_default_location(session: AsyncSession, workspace_id: UUID) -> Location:
    location = await session.scalar(
        select(Location).where(
            Location.workspace_id == workspace_id,
            Location.code == DEFAULT_LOCATION_CODE,
        )
    )
    if location is None:
        location = Location(
            workspace_id=workspace_id,
            name="Default location",
            code=DEFAULT_LOCATION_CODE,
            type="store",
            metadata_json={"system_default": True},
        )
        session.add(location)
        await session.flush()
    return location


async def resolve_location(session: AsyncSession, workspace_id: UUID, code: str | None) -> Location:
    if code is None:
        return await get_or_create_default_location(session, workspace_id)
    location = await session.scalar(
        select(Location).where(
            Location.workspace_id == workspace_id,
            Location.code == code.strip().upper(),
            Location.is_active.is_(True),
        )
    )
    if location is None:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "UNKNOWN_LOCATION",
            f'Không tìm thấy location code "{code}" trong workspace.',
        )
    return location


async def upsert_variant_location(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    location: Location,
    variant: ProductVariant,
    quantity: int | None,
    quantity_supplied: bool,
    price_override: Decimal | None = None,
    price_supplied: bool = False,
    compare_at_price_override: Decimal | None = None,
    compare_price_supplied: bool = False,
    is_active: bool | None = True,
) -> tuple[LocationVariant, InventoryLevel]:
    assignment = await session.get(
        LocationVariant,
        {"workspace_id": workspace_id, "location_id": location.id, "variant_id": variant.id},
    )
    if assignment is None:
        assignment = LocationVariant(
            workspace_id=workspace_id,
            location_id=location.id,
            variant_id=variant.id,
            is_active=is_active if is_active is not None else True,
        )
        session.add(assignment)
    else:
        if is_active is not None:
            assignment.is_active = is_active
    if price_supplied:
        assignment.price_override = price_override
    if compare_price_supplied:
        assignment.compare_at_price_override = compare_at_price_override
    assignment.updated_at = datetime.now(UTC)

    inventory = await session.get(
        InventoryLevel,
        {"workspace_id": workspace_id, "location_id": location.id, "variant_id": variant.id},
    )
    if inventory is None:
        inventory = InventoryLevel(
            workspace_id=workspace_id,
            location_id=location.id,
            variant_id=variant.id,
            quantity=quantity if quantity_supplied else None,
        )
        session.add(inventory)
    elif quantity_supplied:
        inventory.quantity = quantity
        inventory.updated_at = datetime.now(UTC)
    await session.flush()
    return assignment, inventory


class CatalogScopeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _authorize(self, user: User, workspace_id: UUID, *, write: bool = False) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN, "FORBIDDEN", "Bạn không có quyền thay đổi catalog."
            )

    async def _location(self, workspace_id: UUID, location_id: int) -> Location:
        location = await self.session.scalar(
            select(Location).where(
                Location.workspace_id == workspace_id,
                Location.id == location_id,
            )
        )
        if location is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy location.")
        return location

    async def _collection(self, workspace_id: UUID, collection_id: int) -> CatalogCollection:
        collection = await self.session.scalar(
            select(CatalogCollection).where(
                CatalogCollection.workspace_id == workspace_id,
                CatalogCollection.id == collection_id,
            )
        )
        if collection is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy collection.")
        return collection

    @staticmethod
    def _location_response(location: Location) -> LocationResponse:
        return LocationResponse(
            id=location.id,
            name=location.name,
            code=location.code,
            type=cast(Any, location.type),
            address=cast(Any, location.address_json or {}),
            metadata=cast(Any, location.metadata_json or {}),
            is_active=location.is_active,
            archived_at=location.archived_at,
            created_at=location.created_at,
            updated_at=location.updated_at,
        )

    async def list_locations(
        self, user: User, workspace_id: UUID, *, include_archived: bool = False
    ) -> list[LocationResponse]:
        await self._authorize(user, workspace_id)
        statement = select(Location).where(Location.workspace_id == workspace_id)
        if not include_archived:
            statement = statement.where(Location.is_active.is_(True))
        locations = list((await self.session.scalars(statement.order_by(Location.name))).all())
        return [self._location_response(location) for location in locations]

    async def get_location(
        self, user: User, workspace_id: UUID, location_id: int
    ) -> LocationResponse:
        await self._authorize(user, workspace_id)
        return self._location_response(await self._location(workspace_id, location_id))

    async def create_location(
        self, user: User, workspace_id: UUID, payload: LocationCreateRequest
    ) -> LocationResponse:
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                location = Location(
                    workspace_id=workspace_id,
                    name=payload.name,
                    code=payload.code,
                    type=payload.type,
                    address_json=cast(dict[str, object], payload.address),
                    metadata_json=cast(dict[str, object], payload.metadata),
                )
                self.session.add(location)
                await self.session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT, "LOCATION_CODE_CONFLICT", "Location code đã tồn tại."
            ) from exc
        return self._location_response(location)

    async def update_location(
        self,
        user: User,
        workspace_id: UUID,
        location_id: int,
        payload: LocationUpdateRequest,
    ) -> LocationResponse:
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                location = await self._location(workspace_id, location_id)
                for field in payload.model_fields_set:
                    value = getattr(payload, field)
                    if field in {"name", "type"} and value is None:
                        raise ApiError(
                            status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "VALIDATION_ERROR",
                            f"{field} cannot be null",
                        )
                    target = {"address": "address_json", "metadata": "metadata_json"}.get(
                        field, field
                    )
                    setattr(location, target, value)
                if payload.is_active is True:
                    location.archived_at = None
                location.updated_at = datetime.now(UTC)
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT, "LOCATION_CODE_CONFLICT", "Location code đã tồn tại."
            ) from exc
        return self._location_response(location)

    async def archive_location(self, user: User, workspace_id: UUID, location_id: int) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            location = await self._location(workspace_id, location_id)
            location.is_active = False
            location.archived_at = datetime.now(UTC)
            location.updated_at = location.archived_at

    async def list_location_variants(
        self,
        user: User,
        workspace_id: UUID,
        location_id: int,
        *,
        query: str | None = None,
        active: bool | None = None,
    ) -> list[LocationVariantResponse]:
        await self._authorize(user, workspace_id)
        location = await self._location(workspace_id, location_id)
        statement = (
            select(LocationVariant, InventoryLevel, ProductVariant, Product)
            .join(
                ProductVariant,
                and_(
                    ProductVariant.workspace_id == LocationVariant.workspace_id,
                    ProductVariant.id == LocationVariant.variant_id,
                ),
            )
            .join(
                Product,
                and_(
                    Product.workspace_id == ProductVariant.workspace_id,
                    Product.id == ProductVariant.product_id,
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
                LocationVariant.workspace_id == workspace_id,
                LocationVariant.location_id == location_id,
            )
        )
        if active is not None:
            statement = statement.where(LocationVariant.is_active.is_(active))
        if query:
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(Product.name.ilike(pattern), ProductVariant.variant_sku.ilike(pattern))
            )
        rows = (
            await self.session.execute(statement.order_by(Product.name, ProductVariant.id))
        ).all()
        return [self._variant_response(location, *row) for row in rows]

    @staticmethod
    def _variant_response(
        location: Location,
        assignment: LocationVariant,
        inventory: InventoryLevel | None,
        variant: ProductVariant,
        product: Product,
    ) -> LocationVariantResponse:
        base_price = variant.price_override if variant.price_override is not None else product.price
        return LocationVariantResponse(
            location_id=location.id,
            location_name=location.name,
            product_id=product.id,
            product_name=product.name,
            variant_id=variant.id,
            variant_sku=variant.variant_sku,
            is_active=assignment.is_active,
            base_price=base_price,
            price_override=assignment.price_override,
            effective_price=(
                assignment.price_override if assignment.price_override is not None else base_price
            ),
            compare_at_price_override=assignment.compare_at_price_override,
            quantity=inventory.quantity if inventory is not None else None,
            updated_at=assignment.updated_at,
        )

    async def update_location_variant(
        self,
        user: User,
        workspace_id: UUID,
        location_id: int,
        variant_id: int,
        payload: LocationVariantUpdateRequest,
    ) -> LocationVariantResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            location = await self._location(workspace_id, location_id)
            variant = await self.session.scalar(
                select(ProductVariant).where(
                    ProductVariant.workspace_id == workspace_id,
                    ProductVariant.id == variant_id,
                )
            )
            if variant is None:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy variant.")
            assignment, inventory = await upsert_variant_location(
                self.session,
                workspace_id=workspace_id,
                location=location,
                variant=variant,
                quantity=payload.quantity,
                quantity_supplied="quantity" in payload.model_fields_set,
                price_override=payload.price_override,
                price_supplied="price_override" in payload.model_fields_set,
                compare_at_price_override=payload.compare_at_price_override,
                compare_price_supplied="compare_at_price_override" in payload.model_fields_set,
                is_active=payload.is_active,
            )
            if "metadata" in payload.model_fields_set:
                assignment.metadata_json = cast(dict[str, object], payload.metadata or {})
            product = await self.session.scalar(
                select(Product).where(
                    Product.workspace_id == workspace_id,
                    Product.id == variant.product_id,
                )
            )
            assert product is not None
        return self._variant_response(location, assignment, inventory, variant, product)

    async def _collection_response(self, collection: CatalogCollection) -> CollectionResponse:
        product_ids = list(
            (
                await self.session.scalars(
                    select(CatalogCollectionProduct.product_id)
                    .where(
                        CatalogCollectionProduct.workspace_id == collection.workspace_id,
                        CatalogCollectionProduct.collection_id == collection.id,
                    )
                    .order_by(CatalogCollectionProduct.product_id)
                )
            ).all()
        )
        return CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            is_active=collection.is_active,
            archived_at=collection.archived_at,
            product_ids=product_ids,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

    async def list_collections(
        self, user: User, workspace_id: UUID, *, include_archived: bool = False
    ) -> list[CollectionResponse]:
        await self._authorize(user, workspace_id)
        statement = select(CatalogCollection).where(CatalogCollection.workspace_id == workspace_id)
        if not include_archived:
            statement = statement.where(CatalogCollection.is_active.is_(True))
        collections = list(
            (await self.session.scalars(statement.order_by(CatalogCollection.name))).all()
        )
        return [await self._collection_response(collection) for collection in collections]

    async def get_collection(
        self, user: User, workspace_id: UUID, collection_id: int
    ) -> CollectionResponse:
        await self._authorize(user, workspace_id)
        return await self._collection_response(await self._collection(workspace_id, collection_id))

    async def list_collection_products(
        self, user: User, workspace_id: UUID, collection_id: int
    ) -> list[CollectionProductResponse]:
        await self._authorize(user, workspace_id)
        await self._collection(workspace_id, collection_id)
        products = list(
            (
                await self.session.scalars(
                    select(Product)
                    .join(
                        CatalogCollectionProduct,
                        and_(
                            CatalogCollectionProduct.workspace_id == Product.workspace_id,
                            CatalogCollectionProduct.product_id == Product.id,
                        ),
                    )
                    .where(
                        CatalogCollectionProduct.workspace_id == workspace_id,
                        CatalogCollectionProduct.collection_id == collection_id,
                    )
                    .order_by(Product.name, Product.id)
                )
            ).all()
        )
        return [
            CollectionProductResponse(
                id=product.id,
                product_sku=product.product_sku,
                name=product.name,
                category=product.category,
                status=cast(Any, product.status),
            )
            for product in products
        ]

    async def create_collection(
        self, user: User, workspace_id: UUID, payload: CollectionCreateRequest
    ) -> CollectionResponse:
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                collection = CatalogCollection(workspace_id=workspace_id, **payload.model_dump())
                self.session.add(collection)
                await self.session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT, "COLLECTION_NAME_CONFLICT", "Tên collection đã tồn tại."
            ) from exc
        return await self._collection_response(collection)

    async def update_collection(
        self,
        user: User,
        workspace_id: UUID,
        collection_id: int,
        payload: CollectionUpdateRequest,
    ) -> CollectionResponse:
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                collection = await self._collection(workspace_id, collection_id)
                for field in payload.model_fields_set:
                    value = getattr(payload, field)
                    if field == "name" and value is None:
                        raise ApiError(
                            status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "VALIDATION_ERROR",
                            "name cannot be null",
                        )
                    setattr(collection, field, value)
                if payload.is_active is True:
                    collection.archived_at = None
                collection.updated_at = datetime.now(UTC)
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT, "COLLECTION_NAME_CONFLICT", "Tên collection đã tồn tại."
            ) from exc
        return await self._collection_response(collection)

    async def archive_collection(self, user: User, workspace_id: UUID, collection_id: int) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            collection = await self._collection(workspace_id, collection_id)
            collection.is_active = False
            collection.archived_at = datetime.now(UTC)
            collection.updated_at = collection.archived_at

    async def set_collection_product(
        self,
        user: User,
        workspace_id: UUID,
        collection_id: int,
        product_id: int,
        *,
        assigned: bool,
    ) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            await self._collection(workspace_id, collection_id)
            product = await self.session.scalar(
                select(Product).where(
                    Product.workspace_id == workspace_id, Product.id == product_id
                )
            )
            if product is None:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy sản phẩm.")
            key = {
                "workspace_id": workspace_id,
                "collection_id": collection_id,
                "product_id": product_id,
            }
            relation = await self.session.get(CatalogCollectionProduct, key)
            if assigned and relation is None:
                self.session.add(CatalogCollectionProduct(**key))
            elif not assigned and relation is not None:
                await self.session.delete(relation)
