from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.runtime import GroundedAgentResponse
from agent_hub_api.catalog.models import ProductImage
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.widget.models import WidgetCatalogImageGrant
from agent_hub_api.widget.public_schemas import (
    PublicAvailabilitySummary,
    PublicGroundedResponse,
    PublicPriceSummary,
    PublicProductCard,
    PublicProductImage,
    PublicProductVariant,
    PublicSourceReference,
)


def _decimal_string(value: object | None) -> str | None:
    return None if value is None else str(value)


def _safe_product_url(value: str | None, allowed_origin: str) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    default_port = 80 if parsed.scheme == "http" else 443
    port = parsed.port
    host = (
        f"[{parsed.hostname.casefold()}]"
        if ":" in parsed.hostname
        else parsed.hostname.casefold()
    )
    origin = f"{parsed.scheme}://{host}"
    if port not in {None, default_port}:
        origin = f"{origin}:{port}"
    return value if origin == allowed_origin else None


async def to_public_grounded_response(
    response: GroundedAgentResponse,
    *,
    allowed_origin: str,
    session: AsyncSession,
    workspace_id: UUID,
    widget_session_id: int,
    grant_expires_at: datetime,
    include_managed_images: bool,
) -> PublicGroundedResponse:
    image_ids = {
        image.image_id
        for card in response.product_cards
        for image in card.images
        if image.kind == "managed"
    }
    image_urls: dict[int, PublicProductImage] = {}
    if include_managed_images and image_ids:
        async with session.begin():
            images = list(
                await session.scalars(
                    select(ProductImage).where(
                        ProductImage.workspace_id == workspace_id,
                        ProductImage.id.in_(image_ids),
                        ProductImage.status == "active",
                        ProductImage.object_key.is_not(None),
                    )
                )
            )
            existing = {
                grant.product_image_id: grant
                for grant in await session.scalars(
                    select(WidgetCatalogImageGrant).where(
                        WidgetCatalogImageGrant.workspace_id == workspace_id,
                        WidgetCatalogImageGrant.session_id == widget_session_id,
                        WidgetCatalogImageGrant.product_image_id.in_(image_ids),
                    )
                )
            }
            for image in images:
                grant = existing.get(image.id)
                if grant is None:
                    grant = WidgetCatalogImageGrant(
                        public_id=new_uuid_v7(),
                        workspace_id=workspace_id,
                        session_id=widget_session_id,
                        product_image_id=image.id,
                        expires_at=grant_expires_at,
                    )
                    session.add(grant)
                    existing[image.id] = grant
                image_urls[image.id] = PublicProductImage(
                    url=f"/api/v1/widget/product-images/{grant.public_id}",
                    alt_text=image.alt_text,
                )
    cards = [
        PublicProductCard(
            card_id=f"product_{index}",
            sku=card.sku,
            name=card.name,
            product_url=_safe_product_url(card.product_url, allowed_origin),
            currency=card.currency,
            price=PublicPriceSummary(
                kind=card.price.kind,
                minimum=_decimal_string(card.price.minimum),
                maximum=_decimal_string(card.price.maximum),
            ),
            availability=PublicAvailabilitySummary(
                total_locations=card.availability.total_locations,
                in_stock_locations=card.availability.in_stock_locations,
                out_of_stock_locations=card.availability.out_of_stock_locations,
                unknown_locations=card.availability.unknown_locations,
            ),
            options=card.options,
            attributes=card.attributes,
            variants=[
                PublicProductVariant(
                    sku=variant.sku,
                    name=variant.name,
                    options=variant.options,
                    attributes=variant.attributes,
                    inventory_state=variant.inventory_state,
                )
                for variant in card.variants
            ],
            images=[
                image_urls[image.image_id]
                for image in card.images
                if image.kind == "managed" and image.image_id in image_urls
            ],
        )
        for index, card in enumerate(response.product_cards, start=1)
    ]
    sources = [
        PublicSourceReference(
            source_id=f"source_{index}",
            title=source.document_title,
            locator=source.source_locator,
        )
        for index, source in enumerate(response.sources, start=1)
    ]
    return PublicGroundedResponse(
        text=response.text,
        product_cards=cards,
        sources=sources,
        usage=response.usage.model_dump(mode="json"),
    )
