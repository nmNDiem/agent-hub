from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, JsonValue, field_serializer, field_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
LocationType = Literal["store", "warehouse", "showroom", "service", "online", "other"]


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class LocationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    type: LocationType = "store"
    address: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        cleaned = clean_optional_text(value)
        return cleaned.upper() if cleaned is not None else None


class LocationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    code: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    type: LocationType | None = None
    address: dict[str, JsonValue] | None = None
    metadata: dict[str, JsonValue] | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return clean_optional_text(value)

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        cleaned = clean_optional_text(value)
        return cleaned.upper() if cleaned is not None else None


class LocationResponse(BaseModel):
    id: int
    name: str
    code: str | None
    type: LocationType
    address: dict[str, JsonValue]
    metadata: dict[str, JsonValue]
    is_active: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LocationVariantUpdateRequest(BaseModel):
    is_active: bool | None = None
    price_override: Money | None = None
    compare_at_price_override: Money | None = None
    quantity: int | None = Field(default=None, ge=0)
    metadata: dict[str, JsonValue] | None = None


class LocationVariantResponse(BaseModel):
    location_id: int
    location_name: str
    product_id: int
    product_name: str
    variant_id: int
    variant_sku: str | None
    is_active: bool
    base_price: Decimal | None
    price_override: Decimal | None
    effective_price: Decimal | None
    compare_at_price_override: Decimal | None
    quantity: int | None
    updated_at: datetime

    @field_serializer(
        "base_price",
        "price_override",
        "effective_price",
        "compare_at_price_override",
        when_used="json",
    )
    def serialize_money(self, value: Decimal | None) -> str | None:
        return format(value, ".2f") if value is not None else None


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return clean_optional_text(value)


class CollectionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    is_active: bool | None = None

    @field_validator("name", "description")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return clean_optional_text(value)


class CollectionResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    archived_at: datetime | None
    product_ids: list[int]
    created_at: datetime
    updated_at: datetime


class CollectionProductResponse(BaseModel):
    id: int
    product_sku: str | None
    name: str
    category: str | None
    status: Literal["active", "archived"]
