from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

InventoryState = Literal["in_stock", "out_of_stock", "unknown"]
PriceSummaryKind = Literal["exact", "range", "unknown"]


@dataclass(frozen=True)
class AuthorizedCatalogScope:
    """Tenant scope resolved by a trusted authorization boundary."""

    workspace_id: UUID
    allowed_location_ids: frozenset[int] | None = None
    allowed_collection_ids: frozenset[int] | None = None


@dataclass(frozen=True)
class CatalogQuery:
    """Search intent. Requested scope can narrow, but never widen, authorization."""

    text: str | None = None
    brand: str | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    in_stock: bool | None = None
    options: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()
    requested_location_ids: frozenset[int] | None = None
    requested_collection_ids: frozenset[int] | None = None
    limit: int = 20


@dataclass(frozen=True)
class CatalogPriceSummary:
    kind: PriceSummaryKind
    minimum: Decimal | None
    maximum: Decimal | None


@dataclass(frozen=True)
class CatalogAvailabilitySummary:
    total_locations: int
    in_stock_locations: int
    out_of_stock_locations: int
    unknown_locations: int


@dataclass(frozen=True)
class CatalogAvailability:
    location_id: int
    location_name: str
    location_code: str | None
    quantity: int | None
    inventory_state: InventoryState
    inventory_updated_at: datetime | None
    effective_price: Decimal | None


@dataclass(frozen=True)
class CatalogVariantReadModel:
    id: int
    sku: str | None
    name: str | None
    inventory_policy: str
    options: Mapping[str, str]
    attributes: Mapping[str, object]
    availability: tuple[CatalogAvailability, ...]


@dataclass(frozen=True)
class CatalogProductReadModel:
    id: int
    sku: str | None
    name: str
    brand: str | None
    category: str | None
    currency: str
    base_price: Decimal | None
    product_url: str | None
    attributes: Mapping[str, object]
    price: CatalogPriceSummary
    availability: CatalogAvailabilitySummary
    variants: tuple[CatalogVariantReadModel, ...]
    updated_at: datetime
