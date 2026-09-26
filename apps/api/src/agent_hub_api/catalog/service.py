from __future__ import annotations

import base64
import hashlib
import io
import json
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

from fastapi import status
from PIL import Image, UnidentifiedImageError
from pydantic import JsonValue
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.catalog.csv_import import ParsedCatalogCsv, parse_catalog_csv
from agent_hub_api.catalog.models import (
    CatalogImport,
    InventoryLevel,
    Location,
    LocationVariant,
    Product,
    ProductImage,
    ProductVariant,
    SizeGuide,
)
from agent_hub_api.catalog.options import load_variant_options, set_variant_options
from agent_hub_api.catalog.repository import CatalogRepository
from agent_hub_api.catalog.schemas import (
    CleanupResponse,
    ImageResponse,
    ImageUrlResponse,
    ImportCommitResponse,
    ImportErrorResponse,
    ImportPreviewResponse,
    ProductCreateRequest,
    ProductDetailResponse,
    ProductListResponse,
    ProductSummaryResponse,
    ProductUpdateRequest,
    SizeGuideRequest,
    SizeGuideResponse,
    VariantCreateRequest,
    VariantLocationAvailabilityResponse,
    VariantResponse,
    VariantUpdateRequest,
)
from agent_hub_api.catalog.scope_service import (
    get_or_create_default_location,
    upsert_variant_location,
)
from agent_hub_api.catalog.storage import CatalogStorage, StorageError
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.service import WorkspaceService

CatalogRole = Literal["owner", "admin", "member"]


def encode_cursor(created_at: datetime, item_id: int) -> str:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": item_id}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[datetime | None, int | None]:
    if cursor is None:
        return None, None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        item_id = int(payload["id"])
        if created_at.tzinfo is None or item_id < 1:
            raise ValueError
        return created_at, item_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_CURSOR",
            "Con trá» phÃ¢n trang khÃ´ng há»£p lá»‡.",
        ) from exc


def variant_response(
    variant: ProductVariant,
    product_price: Decimal | None,
    options: dict[str, str] | None = None,
    availability: list[VariantLocationAvailabilityResponse] | None = None,
) -> VariantResponse:
    effective_price = (
        variant.price_override if variant.price_override is not None else product_price
    )
    return VariantResponse(
        id=variant.id,
        variant_sku=variant.variant_sku,
        name=variant.name,
        color=(options or {}).get("Color", variant.color),
        size=(options or {}).get("Size", variant.size),
        options=options or {},
        price_override=variant.price_override,
        effective_price=effective_price,
        stock_quantity=next(
            (item.quantity for item in availability or [] if item.location_code == "DEFAULT"),
            None,
        ),
        availability=availability or [],
        status=cast(Literal["active", "archived"], variant.status),
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    )


def image_response(image: ProductImage) -> ImageResponse:
    return ImageResponse(
        id=image.id,
        variant_id=image.variant_id,
        original_filename=image.original_filename,
        source_url=image.source_url,
        content_type=image.content_type,
        byte_size=image.byte_size,
        width=image.width,
        height=image.height,
        alt_text=image.alt_text,
        sort_order=image.sort_order,
        status=cast(Literal["uploading", "active", "cleanup_pending", "deleted"], image.status),
        cleanup_attempts=image.cleanup_attempts,
        created_at=image.created_at,
    )


class CatalogService:
    def __init__(self, session: AsyncSession, settings: Settings, storage: CatalogStorage) -> None:
        self.session = session
        self.settings = settings
        self.storage = storage
        self.repository = CatalogRepository(session)

    async def _authorize(
        self, user: User, workspace_id: UUID, *, write: bool = False
    ) -> CatalogRole:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Báº¡n khÃ´ng cÃ³ quyá»n thay Ä‘á»•i catalog.",
            )
        return cast(CatalogRole, role)

    async def _product_or_404(self, workspace_id: UUID, product_id: int) -> Product:
        product = await self.repository.get_product(workspace_id, product_id)
        if product is None:
            raise ApiError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "KhÃ´ng tÃ¬m tháº¥y sáº£n pháº©m."
            )
        return product

    async def list_products(
        self,
        user: User,
        workspace_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        product_status: str | None,
        category: str | None,
        query: str | None,
    ) -> ProductListResponse:
        await self._authorize(user, workspace_id)
        cursor_created_at, cursor_id = decode_cursor(cursor)
        products, counts, has_more = await self.repository.list_products(
            workspace_id=workspace_id,
            limit=limit,
            status=product_status,
            category=category.strip() if category else None,
            query=query.strip() if query else None,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )
        items = [self._summary(product, counts.get(product.id, 0)) for product in products]
        next_cursor = None
        if has_more and products:
            last = products[-1]
            next_cursor = encode_cursor(last.created_at, last.id)
        return ProductListResponse(items=items, next_cursor=next_cursor)

    def _summary(self, product: Product, variant_count: int) -> ProductSummaryResponse:
        return ProductSummaryResponse(
            id=product.id,
            product_sku=product.product_sku,
            name=product.name,
            category=product.category,
            currency=product.currency,
            price=product.price,
            status=cast(Literal["active", "archived"], product.status),
            variant_count=variant_count,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

    async def get_product(
        self, user: User, workspace_id: UUID, product_id: int
    ) -> ProductDetailResponse:
        await self._authorize(user, workspace_id)
        product = await self._product_or_404(workspace_id, product_id)
        variants, guide, images = await self.repository.get_product_detail_relations(
            workspace_id, product_id
        )
        option_map = await load_variant_options(
            self.session, workspace_id, [variant.id for variant in variants]
        )
        availability = await self._load_availability(workspace_id, variants, product.price)
        return self._detail(product, variants, guide, images, option_map, availability)

    async def _load_availability(
        self, workspace_id: UUID, variants: list[ProductVariant], product_price: Decimal | None
    ) -> dict[int, list[VariantLocationAvailabilityResponse]]:
        if not variants:
            return {}
        rows = (
            await self.session.execute(
                select(LocationVariant, InventoryLevel, Location)
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
                    LocationVariant.workspace_id == workspace_id,
                    LocationVariant.variant_id.in_([variant.id for variant in variants]),
                )
                .order_by(Location.name)
            )
        ).all()
        base_prices = {
            variant.id: variant.price_override
            if variant.price_override is not None
            else product_price
            for variant in variants
        }
        result: dict[int, list[VariantLocationAvailabilityResponse]] = {}
        for assignment, inventory, location in rows:
            base_price = base_prices[assignment.variant_id]
            result.setdefault(assignment.variant_id, []).append(
                VariantLocationAvailabilityResponse(
                    location_id=location.id,
                    location_name=location.name,
                    location_code=location.code,
                    is_active=assignment.is_active and location.is_active,
                    quantity=inventory.quantity if inventory is not None else None,
                    price_override=assignment.price_override,
                    effective_price=(
                        assignment.price_override
                        if assignment.price_override is not None
                        else base_price
                    ),
                )
            )
        return result

    def _detail(
        self,
        product: Product,
        variants: list[ProductVariant],
        guide: SizeGuide | None,
        images: list[ProductImage],
        option_map: dict[int, dict[str, str]],
        availability: dict[int, list[VariantLocationAvailabilityResponse]] | None = None,
    ) -> ProductDetailResponse:
        summary = self._summary(product, sum(variant.status == "active" for variant in variants))
        guide_payload = (
            SizeGuideResponse(
                id=guide.id,
                title=guide.title,
                content=cast(dict[str, JsonValue], guide.content),
                updated_at=guide.updated_at,
            )
            if guide is not None
            else None
        )
        return ProductDetailResponse(
            **summary.model_dump(),
            description=product.description,
            product_url=product.product_url,
            variants=[
                variant_response(
                    variant,
                    product.price,
                    option_map.get(variant.id, {}),
                    (availability or {}).get(variant.id, []),
                )
                for variant in variants
            ],
            size_guide=guide_payload,
            images=[image_response(image) for image in images],
        )

    async def create_product(
        self, user: User, workspace_id: UUID, payload: ProductCreateRequest
    ) -> ProductDetailResponse:
        product = Product(workspace_id=workspace_id, **payload.model_dump())
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                await self.repository.add_product(product)
        except IntegrityError as exc:
            raise self._sku_conflict("product_sku") from exc
        return self._detail(product, [], None, [], {})

    async def update_product(
        self,
        user: User,
        workspace_id: UUID,
        product_id: int,
        payload: ProductUpdateRequest,
    ) -> ProductDetailResponse:
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                product = await self._product_or_404(workspace_id, product_id)
                for field in payload.model_fields_set:
                    value = getattr(payload, field)
                    if field in {"name", "currency"} and value is None:
                        raise ApiError(
                            status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "VALIDATION_ERROR",
                            f"{field} cannot be null",
                        )
                    setattr(product, field, value)
                product.updated_at = datetime.now(UTC)
        except IntegrityError as exc:
            raise self._sku_conflict("product_sku") from exc
        return await self.get_product(user, workspace_id, product_id)

    async def archive_product(self, user: User, workspace_id: UUID, product_id: int) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            product = await self._product_or_404(workspace_id, product_id)
            product.status = "archived"
            product.updated_at = datetime.now(UTC)

    async def create_variant(
        self,
        user: User,
        workspace_id: UUID,
        product_id: int,
        payload: VariantCreateRequest,
    ) -> VariantResponse:
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                product = await self._product_or_404(workspace_id, product_id)
                values = payload.model_dump(exclude={"options", "stock_quantity"})
                variant = ProductVariant(workspace_id=workspace_id, product_id=product_id, **values)
                await self.repository.add_variant(variant)
                default_location = await get_or_create_default_location(self.session, workspace_id)
                await upsert_variant_location(
                    self.session,
                    workspace_id=workspace_id,
                    location=default_location,
                    variant=variant,
                    quantity=payload.stock_quantity,
                    quantity_supplied=True,
                )
                options: dict[str, str | None] = dict(payload.options)
                if payload.color is not None:
                    options["Color"] = payload.color
                if payload.size is not None:
                    options["Size"] = payload.size
                await set_variant_options(
                    self.session, workspace_id, product, variant, options, replace_all=True
                )
        except IntegrityError as exc:
            raise self._sku_conflict("variant_sku") from exc
        option_map = await load_variant_options(self.session, workspace_id, [variant.id])
        availability = await self._load_availability(workspace_id, [variant], product.price)
        return variant_response(
            variant,
            product.price,
            option_map.get(variant.id, {}),
            availability.get(variant.id, []),
        )

    async def update_variant(
        self,
        user: User,
        workspace_id: UUID,
        product_id: int,
        variant_id: int,
        payload: VariantUpdateRequest,
    ) -> VariantResponse:
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                product = await self._product_or_404(workspace_id, product_id)
                variant = await self.repository.get_variant(workspace_id, product_id, variant_id)
                if variant is None:
                    raise ApiError(
                        status.HTTP_404_NOT_FOUND, "NOT_FOUND", "KhÃ´ng tÃ¬m tháº¥y biáº¿n thá»ƒ."
                    )
                for field in payload.model_fields_set - {"options", "stock_quantity"}:
                    setattr(variant, field, getattr(payload, field))
                if "stock_quantity" in payload.model_fields_set:
                    default_location = await get_or_create_default_location(
                        self.session, workspace_id
                    )
                    await upsert_variant_location(
                        self.session,
                        workspace_id=workspace_id,
                        location=default_location,
                        variant=variant,
                        quantity=payload.stock_quantity,
                        quantity_supplied=True,
                    )
                if "options" in payload.model_fields_set:
                    await set_variant_options(
                        self.session,
                        workspace_id,
                        product,
                        variant,
                        dict(payload.options),
                        replace_all=True,
                    )
                else:
                    changed_options: dict[str, str | None] = {}
                    if "color" in payload.model_fields_set:
                        changed_options["Color"] = payload.color
                    if "size" in payload.model_fields_set:
                        changed_options["Size"] = payload.size
                    await set_variant_options(
                        self.session,
                        workspace_id,
                        product,
                        variant,
                        changed_options,
                        replace_all=False,
                    )
                variant.updated_at = datetime.now(UTC)
        except IntegrityError as exc:
            raise self._sku_conflict("variant_sku") from exc
        option_map = await load_variant_options(self.session, workspace_id, [variant.id])
        availability = await self._load_availability(workspace_id, [variant], product.price)
        return variant_response(
            variant,
            product.price,
            option_map.get(variant.id, {}),
            availability.get(variant.id, []),
        )

    async def archive_variant(
        self, user: User, workspace_id: UUID, product_id: int, variant_id: int
    ) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            await self._product_or_404(workspace_id, product_id)
            variant = await self.repository.get_variant(workspace_id, product_id, variant_id)
            if variant is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND, "NOT_FOUND", "KhÃ´ng tÃ¬m tháº¥y biáº¿n thá»ƒ."
                )
            variant.status = "archived"
            variant.updated_at = datetime.now(UTC)

    async def put_size_guide(
        self,
        user: User,
        workspace_id: UUID,
        product_id: int,
        payload: SizeGuideRequest,
    ) -> SizeGuideResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            await self._product_or_404(workspace_id, product_id)
            guide = await self.repository.get_size_guide(workspace_id, product_id)
            if guide is None:
                guide = SizeGuide(
                    workspace_id=workspace_id,
                    product_id=product_id,
                    title=payload.title,
                    content=payload.content,
                )
                self.session.add(guide)
                await self.session.flush()
            else:
                guide.title = payload.title
                guide.content = cast(dict[str, object], payload.content)
                guide.updated_at = datetime.now(UTC)
        return SizeGuideResponse(
            id=guide.id,
            title=guide.title,
            content=cast(dict[str, JsonValue], guide.content),
            updated_at=guide.updated_at,
        )

    async def delete_size_guide(self, user: User, workspace_id: UUID, product_id: int) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            await self._product_or_404(workspace_id, product_id)
            guide = await self.repository.get_size_guide(workspace_id, product_id)
            if guide is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND, "NOT_FOUND", "KhÃ´ng tÃ¬m tháº¥y hÆ°á»›ng dáº«n."
                )
            await self.repository.delete_size_guide(guide)

    def _sku_conflict(self, field: str) -> ApiError:
        return ApiError(
            status.HTTP_409_CONFLICT,
            "SKU_CONFLICT",
            "SKU Ä‘Ã£ Ä‘Æ°á»£c sá»­ dá»¥ng trong workspace, ká»ƒ cáº£ báº£n ghi Ä‘Ã£ lÆ°u trá»¯.",
            details={"field": field},
        )

    async def preview_import(
        self, user: User, workspace_id: UUID, content: bytes
    ) -> ImportPreviewResponse:
        await self._authorize(user, workspace_id, write=True)
        parsed = self._parse_import(content)
        await self._add_database_import_errors(workspace_id, parsed)
        return ImportPreviewResponse(
            payload_sha256=parsed.payload_sha256,
            product_count=len(parsed.products),
            variant_count=parsed.variant_count,
            errors=parsed.errors,
        )

    def _parse_import(self, content: bytes) -> ParsedCatalogCsv:
        return parse_catalog_csv(
            content,
            max_bytes=self.settings.catalog_csv_max_bytes,
            max_rows=self.settings.catalog_csv_max_rows,
        )

    async def _add_database_import_errors(
        self, workspace_id: UUID, parsed: ParsedCatalogCsv
    ) -> None:
        product_rows = {
            product.product.product_sku: product.row
            for product in parsed.products
            if product.product.product_sku is not None
        }
        variant_rows = {
            variant.variant_sku: row
            for product in parsed.products
            for row, variant in product.variants
            if variant.variant_sku is not None
        }
        existing_products = await self.repository.find_product_skus(workspace_id, set(product_rows))
        existing_variants = await self.repository.find_variant_skus(workspace_id, set(variant_rows))
        parsed.errors.extend(
            ImportErrorResponse(
                row=product_rows[sku],
                column="product_sku",
                code="SKU_CONFLICT",
                message="product_sku already exists, including archived products",
            )
            for sku in sorted(existing_products)
        )
        parsed.errors.extend(
            ImportErrorResponse(
                row=variant_rows[sku],
                column="variant_sku",
                code="SKU_CONFLICT",
                message="variant_sku already exists, including archived variants",
            )
            for sku in sorted(existing_variants)
        )

    async def commit_import(
        self,
        user: User,
        workspace_id: UUID,
        *,
        content: bytes,
        preview_sha256: str,
        idempotency_key: str,
    ) -> ImportCommitResponse:
        parsed = self._parse_import(content)
        if not secrets.compare_digest(parsed.payload_sha256, preview_sha256.lower()):
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "PREVIEW_MISMATCH",
                "Tá»‡p CSV Ä‘Ã£ thay Ä‘á»•i sau khi xem trÆ°á»›c.",
            )
        claim = await self._claim_import(user, workspace_id, idempotency_key, parsed.payload_sha256)
        if claim.status == "completed" and claim.result is not None:
            return ImportCommitResponse.model_validate({**claim.result, "replayed": True})
        if claim.status == "failed":
            self._raise_stored_import_failure(claim)
        claim_id = claim.id

        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                await self._add_database_import_errors(workspace_id, parsed)
                if parsed.errors:
                    raise ApiError(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "IMPORT_VALIDATION_FAILED",
                        "CSV cÃ³ dá»¯ liá»‡u khÃ´ng há»£p lá»‡.",
                        details={
                            "errors": [error.model_dump(mode="json") for error in parsed.errors]
                        },
                    )
                for parsed_product in parsed.products:
                    product = Product(
                        workspace_id=workspace_id,
                        **parsed_product.product.model_dump(),
                    )
                    await self.repository.add_product(product)
                    for _, variant_payload in parsed_product.variants:
                        variant = ProductVariant(
                            workspace_id=workspace_id,
                            product_id=product.id,
                            **variant_payload.model_dump(exclude={"options", "stock_quantity"}),
                        )
                        await self.repository.add_variant(variant)
                        default_location = await get_or_create_default_location(
                            self.session, workspace_id
                        )
                        await upsert_variant_location(
                            self.session,
                            workspace_id=workspace_id,
                            location=default_location,
                            variant=variant,
                            quantity=variant_payload.stock_quantity,
                            quantity_supplied=True,
                        )
                        options: dict[str, str | None] = dict(variant_payload.options)
                        if variant_payload.color is not None:
                            options["Color"] = variant_payload.color
                        if variant_payload.size is not None:
                            options["Size"] = variant_payload.size
                        await set_variant_options(
                            self.session,
                            workspace_id,
                            product,
                            variant,
                            options,
                            replace_all=True,
                        )
                stored_claim = await self.repository.get_import_by_key(
                    workspace_id, idempotency_key
                )
                if stored_claim is None or stored_claim.id != claim_id:
                    raise RuntimeError("Catalog import claim disappeared")
                result = ImportCommitResponse(
                    import_id=claim_id,
                    status="completed",
                    product_count=len(parsed.products),
                    variant_count=parsed.variant_count,
                    payload_sha256=parsed.payload_sha256,
                )
                stored_claim.status = "completed"
                stored_claim.result = result.model_dump(mode="json")
                stored_claim.completed_at = datetime.now(UTC)
        except ApiError as exc:
            await self._mark_import_failed(claim_id, workspace_id, exc)
            raise
        except IntegrityError as exc:
            failure = self._sku_conflict("product_sku_or_variant_sku")
            await self._mark_import_failed(claim_id, workspace_id, failure)
            raise failure from exc
        return result

    async def _claim_import(
        self,
        user: User,
        workspace_id: UUID,
        idempotency_key: str,
        payload_sha256: str,
    ) -> CatalogImport:
        normalized_key = idempotency_key.strip()
        if not normalized_key or len(normalized_key) > 128:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "INVALID_IDEMPOTENCY_KEY",
                "Idempotency-Key pháº£i cÃ³ tá»« 1 Ä‘áº¿n 128 kÃ½ tá»±.",
            )
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(seconds=self.settings.catalog_import_lease_seconds)
        claim = CatalogImport(
            workspace_id=workspace_id,
            idempotency_key=normalized_key,
            payload_sha256=payload_sha256,
            status="processing",
            lease_expires_at=lease_expires_at,
        )
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                self.session.add(claim)
                await self.session.flush()
            return claim
        except IntegrityError:
            pass

        existing = await self.repository.get_import_by_key(workspace_id, normalized_key)
        if existing is None:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "IMPORT_CONFLICT",
                "KhÃ´ng thá»ƒ khá»Ÿi táº¡o import.",
            )
        if not secrets.compare_digest(existing.payload_sha256, payload_sha256):
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_PAYLOAD_MISMATCH",
                "Idempotency-Key Ä‘Ã£ Ä‘Æ°á»£c dÃ¹ng vá»›i ná»™i dung khÃ¡c.",
            )
        if existing.status in {"completed", "failed"}:
            return existing
        existing_id = existing.id
        await self.session.rollback()
        async with self.session.begin():
            reclaimed = await self.repository.reclaim_import(
                import_id=existing_id,
                workspace_id=workspace_id,
                now=now,
                lease_expires_at=lease_expires_at,
            )
        if reclaimed:
            reclaimed_claim = await self.session.get(CatalogImport, existing_id)
            if reclaimed_claim is None:
                raise RuntimeError("Reclaimed catalog import disappeared")
            return reclaimed_claim
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "IMPORT_IN_PROGRESS",
            "Import vá»›i Idempotency-Key nÃ y Ä‘ang Ä‘Æ°á»£c xá»­ lÃ½.",
        )

    def _raise_stored_import_failure(self, claim: CatalogImport) -> None:
        result = claim.result or {}
        stored_status = result.get("status_code")
        status_code = (
            stored_status
            if isinstance(stored_status, int)
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise ApiError(
            status_code,
            str(result.get("code", "IMPORT_FAILED")),
            str(result.get("message", "Import Ä‘Ã£ tháº¥t báº¡i.")),
            details=cast(dict[str, object], result.get("details", {})),
        )

    async def _mark_import_failed(self, import_id: int, workspace_id: UUID, exc: ApiError) -> None:
        await self.session.rollback()
        async with self.session.begin():
            claim = await self.session.get(CatalogImport, import_id)
            if claim is not None and claim.workspace_id == workspace_id:
                claim.status = "failed"
                claim.result = {
                    "status_code": exc.status_code,
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
                claim.completed_at = datetime.now(UTC)

    async def upload_image(
        self,
        user: User,
        workspace_id: UUID,
        product_id: int,
        *,
        content: bytes,
        filename: str,
        declared_content_type: str,
        variant_id: int | None,
        alt_text: str | None,
        sort_order: int,
    ) -> ImageResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            await self._product_or_404(workspace_id, product_id)
            if variant_id is not None:
                variant = await self.repository.get_variant(workspace_id, product_id, variant_id)
                if variant is None:
                    raise ApiError(
                        status.HTTP_404_NOT_FOUND, "NOT_FOUND", "KhÃ´ng tÃ¬m tháº¥y biáº¿n thá»ƒ."
                    )
            content_type, width, height = self._validate_image(content, declared_content_type)
            safe_filename = Path(filename).name[:255] or "image"
            object_key = (
                f"workspaces/{workspace_id}/catalog/{product_id}/"
                f"{secrets.token_urlsafe(18)}."
                f"{content_type.split('/')[-1].replace('jpeg', 'jpg')}"
            )
            image = ProductImage(
                workspace_id=workspace_id,
                product_id=product_id,
                variant_id=variant_id,
                object_key=object_key,
                original_filename=safe_filename,
                content_type=content_type,
                byte_size=len(content),
                width=width,
                height=height,
                sha256=hashlib.sha256(content).hexdigest(),
                alt_text=alt_text.strip() if alt_text else None,
                sort_order=sort_order,
                status="uploading",
            )
            await self.repository.add_image(image)
        try:
            await self.storage.upload(
                object_key=object_key, content=content, content_type=content_type
            )
        except StorageError as exc:
            await self._set_cleanup_pending(image.id, workspace_id, "upload_failed")
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "STORAGE_UNAVAILABLE",
                "KhÃ´ng thá»ƒ lÆ°u áº£nh. Metadata Ä‘Ã£ Ä‘Æ°á»£c Ä‘Ã¡nh dáº¥u chá» dá»n dáº¹p.",
                details={"image_id": image.id, "cleanup_pending": True},
            ) from exc
        async with self.session.begin():
            stored = await self.session.get(ProductImage, image.id)
            if stored is None or stored.workspace_id != workspace_id:
                raise RuntimeError("Catalog image metadata disappeared")
            stored.status = "active"
            stored.updated_at = datetime.now(UTC)
        return image_response(stored)

    def _validate_image(self, content: bytes, declared_content_type: str) -> tuple[str, int, int]:
        if not content or len(content) > self.settings.catalog_image_max_bytes:
            raise ApiError(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "IMAGE_TOO_LARGE",
                "áº¢nh vá»£t quÃ¡ giá»›i háº¡n dung lÆ°á»£ng.",
            )
        allowed = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
        try:
            with Image.open(io.BytesIO(content)) as source:
                source.verify()
            with Image.open(io.BytesIO(content)) as source:
                image_format = source.format or ""
                width, height = source.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ApiError(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "INVALID_IMAGE",
                "Tá»‡p táº£i lÃªn khÃ´ng pháº£i áº£nh há»£p lá»‡.",
            ) from exc
        actual_content_type = allowed.get(image_format)
        if actual_content_type is None or declared_content_type.lower() != actual_content_type:
            raise ApiError(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "IMAGE_TYPE_MISMATCH",
                "Äá»‹nh dáº¡ng áº£nh khÃ´ng khá»›p vá»›i ná»™i dung tá»‡p.",
            )
        if width * height > self.settings.catalog_image_max_pixels:
            raise ApiError(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "IMAGE_PIXELS_EXCEEDED",
                "KÃ­ch thÆ°á»›c pixel cá»§a áº£nh quÃ¡ lá»›n.",
            )
        return actual_content_type, width, height

    async def get_image_url(
        self, user: User, workspace_id: UUID, product_id: int, image_id: int
    ) -> ImageUrlResponse:
        await self._authorize(user, workspace_id)
        await self._product_or_404(workspace_id, product_id)
        image = await self.repository.get_image(workspace_id, product_id, image_id)
        if image is None or image.status != "active":
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "KhÃ´ng tÃ¬m tháº¥y áº£nh.")
        if image.object_key is None:
            if image.source_url is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND, "NOT_FOUND", "KhÃ´ng tÃ¬m tháº¥y nguá»“n áº£nh."
                )
            return ImageUrlResponse(url=image.source_url, expires_in=0)
        try:
            url = await self.storage.create_signed_url(
                object_key=image.object_key,
                expires_in=self.settings.storage_signed_url_seconds,
            )
        except StorageError as exc:
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "STORAGE_UNAVAILABLE",
                "KhÃ´ng thá»ƒ táº¡o liÃªn káº¿t áº£nh táº¡m thá»i.",
            ) from exc
        return ImageUrlResponse(url=url, expires_in=self.settings.storage_signed_url_seconds)

    async def delete_image(
        self, user: User, workspace_id: UUID, product_id: int, image_id: int
    ) -> CleanupResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            await self._product_or_404(workspace_id, product_id)
            image = await self.repository.get_image(workspace_id, product_id, image_id)
            if image is None:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "KhÃ´ng tÃ¬m tháº¥y áº£nh.")
            image.status = "cleanup_pending"
            image.updated_at = datetime.now(UTC)
        return await self._attempt_cleanup(image)

    async def retry_image_cleanup(
        self, user: User, workspace_id: UUID, product_id: int, image_id: int
    ) -> CleanupResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            await self._product_or_404(workspace_id, product_id)
            image = await self.repository.get_image(workspace_id, product_id, image_id)
            if image is None or image.status != "cleanup_pending":
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "CLEANUP_NOT_PENDING",
                    "áº¢nh khÃ´ng á»Ÿ tráº¡ng thÃ¡i chá» dá»n dáº¹p.",
                )
        return await self._attempt_cleanup(image)

    async def _attempt_cleanup(self, image: ProductImage) -> CleanupResponse:
        if image.object_key is None:
            async with self.session.begin():
                image.status = "deleted"
                image.updated_at = datetime.now(UTC)
            return CleanupResponse(
                image_id=image.id, status="deleted", message="ÄÃ£ xÃ³a metadata áº£nh."
            )
        try:
            await self.storage.delete(object_key=image.object_key)
        except StorageError:
            await self._set_cleanup_pending(image.id, image.workspace_id, "storage_delete_failed")
            return CleanupResponse(
                image_id=image.id,
                status="cleanup_pending",
                message=(
                    "Metadata Ä‘Ã£ Ä‘Æ°á»£c lÆ°u; Storage cleanup tháº¥t báº¡i "
                    "vÃ  cáº§n thá»­ láº¡i."
                ),
            )
        async with self.session.begin():
            stored = await self.session.get(ProductImage, image.id)
            if stored is None or stored.workspace_id != image.workspace_id:
                raise RuntimeError("Catalog image metadata disappeared")
            stored.status = "deleted"
            stored.last_cleanup_error = None
            stored.updated_at = datetime.now(UTC)
        return CleanupResponse(
            image_id=image.id, status="deleted", message="áº¢nh Ä‘Ã£ Ä‘Æ°á»£c dá»n dáº¹p."
        )

    async def _set_cleanup_pending(
        self, image_id: int, workspace_id: UUID, error_code: str
    ) -> None:
        await self.session.rollback()
        async with self.session.begin():
            stored = await self.session.get(ProductImage, image_id)
            if stored is not None and stored.workspace_id == workspace_id:
                stored.status = "cleanup_pending"
                stored.cleanup_attempts += 1
                stored.last_cleanup_error = error_code
                stored.updated_at = datetime.now(UTC)
