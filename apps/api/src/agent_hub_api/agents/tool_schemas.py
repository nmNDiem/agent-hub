from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_serializer, field_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


def _clean_filters(value: dict[str, str]) -> dict[str, str]:
    if len(value) > 20:
        raise ValueError("A tool request cannot contain more than 20 filters")
    cleaned = {name.strip(): item.strip() for name, item in value.items()}
    if any(
        not name or not item or len(name) > 100 or len(item) > 500
        for name, item in cleaned.items()
    ):
        raise ValueError("Filter names and values must be non-empty and within length limits")
    return cleaned


def _clean_ids(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    if any(item < 1 for item in value):
        raise ValueError("Scope IDs must be positive integers")
    return sorted(set(value))


class SearchProductsToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=200)
    brand: str | None = Field(default=None, max_length=160)
    min_price: Money | None = None
    max_price: Money | None = None
    in_stock: bool | None = None
    options: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, str] = Field(default_factory=dict)
    location_ids: list[int] | None = None
    collection_ids: list[int] | None = None
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("query", "brand")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("options", "attributes")
    @classmethod
    def clean_filters(cls, value: dict[str, str]) -> dict[str, str]:
        return _clean_filters(value)

    @field_validator("location_ids", "collection_ids")
    @classmethod
    def clean_ids(cls, value: list[int] | None) -> list[int] | None:
        return _clean_ids(value)


class GetProductDetailToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(ge=1)
    location_ids: list[int] | None = None
    collection_ids: list[int] | None = None

    @field_validator("location_ids", "collection_ids")
    @classmethod
    def clean_ids(cls, value: list[int] | None) -> list[int] | None:
        return _clean_ids(value)


class CheckStockToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: int = Field(ge=1)
    location_ids: list[int] | None = None

    @field_validator("location_ids")
    @classmethod
    def clean_ids(cls, value: list[int] | None) -> list[int] | None:
        return _clean_ids(value)


class CatalogToolPriceSummary(BaseModel):
    kind: Literal["exact", "range", "unknown"]
    minimum: Decimal | None
    maximum: Decimal | None

    @field_serializer("minimum", "maximum", when_used="json")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return format(value, ".2f") if value is not None else None


class CatalogToolAvailabilitySummary(BaseModel):
    total_locations: int
    in_stock_locations: int
    out_of_stock_locations: int
    unknown_locations: int


class CatalogToolAvailability(BaseModel):
    location_id: int
    location_name: str
    location_code: str | None
    quantity: int | None
    inventory_state: Literal["in_stock", "out_of_stock", "unknown"]
    inventory_updated_at: datetime | None
    effective_price: Decimal | None

    @field_serializer("effective_price", when_used="json")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return format(value, ".2f") if value is not None else None


class CatalogToolVariant(BaseModel):
    id: int
    sku: str | None
    name: str | None
    inventory_policy: str
    options: dict[str, str]
    attributes: dict[str, JsonValue]
    color: str | None
    size: str | None
    availability: list[CatalogToolAvailability]


class CatalogToolImageReference(BaseModel):
    image_id: int
    variant_id: int | None
    kind: Literal["managed", "remote"]
    alt_text: str | None
    sort_order: int


class CatalogToolSizeGuide(BaseModel):
    title: str
    content: dict[str, JsonValue]
    updated_at: datetime


class CatalogToolProduct(BaseModel):
    id: int
    sku: str | None
    name: str
    description: str | None
    brand: str | None
    category: str | None
    currency: str
    base_price: Decimal | None
    product_url: str | None
    attributes: dict[str, JsonValue]
    price: CatalogToolPriceSummary
    availability: CatalogToolAvailabilitySummary
    variants: list[CatalogToolVariant]
    images: list[CatalogToolImageReference]
    size_guide: CatalogToolSizeGuide | None
    updated_at: datetime

    @field_serializer("base_price", when_used="json")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return format(value, ".2f") if value is not None else None


class SearchProductsToolResult(BaseModel):
    items: list[CatalogToolProduct]


class CheckStockToolResult(BaseModel):
    variant_id: int
    sku: str | None
    inventory_policy: str
    availability: list[CatalogToolAvailability]
