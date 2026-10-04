from urllib.parse import urlsplit

from agent_hub_api.agents.runtime import GroundedAgentResponse
from agent_hub_api.widget.public_schemas import (
    PublicAvailabilitySummary,
    PublicGroundedResponse,
    PublicPriceSummary,
    PublicProductCard,
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


def to_public_grounded_response(
    response: GroundedAgentResponse, *, allowed_origin: str
) -> PublicGroundedResponse:
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
