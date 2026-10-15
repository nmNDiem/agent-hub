from collections.abc import Iterable, Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.analytics.models import AnalyticsEvent


def product_ids_from_response(response_json: Mapping[str, object]) -> tuple[int, ...]:
    raw_cards = response_json.get("product_cards")
    if not isinstance(raw_cards, list):
        return ()
    product_ids: set[int] = set()
    for raw_card in raw_cards:
        if not isinstance(raw_card, dict):
            continue
        product_id = raw_card.get("product_id")
        if isinstance(product_id, int) and not isinstance(product_id, bool) and product_id > 0:
            product_ids.add(product_id)
    return tuple(sorted(product_ids))


def record_product_impressions(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    agent_id: int,
    conversation_id: int,
    message_id: int,
    channel: str,
    product_ids: Iterable[int],
    occurred_at: datetime,
) -> None:
    session.add_all(
        [
            AnalyticsEvent(
                workspace_id=workspace_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                message_id=message_id,
                product_id=product_id,
                channel=channel,
                event_type="product_impression",
                occurred_at=occurred_at,
            )
            for product_id in sorted(set(product_ids))
        ]
    )
