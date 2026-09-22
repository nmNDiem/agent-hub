import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, JsonValue, field_serializer, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
CatalogStatus = Literal["active", "archived"]


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def normalize_sku(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    return normalized.upper() if normalized is not None else None


def validate_product_url(value: str | None) -> str | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Product URL must be an absolute HTTP or HTTPS URL")
    return normalized


class ProductCreateRequest(BaseModel):
    product_sku: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    category: str | None = Field(default=None, max_length=120)
    currency: str = Field(default="VND", pattern=r"^[A-Z]{3}$")
    price: Money | None = None
    product_url: str | None = Field(default=None, max_length=2048)

    @field_validator("product_sku")
    @classmethod
    def clean_sku(cls, value: str | None) -> str | None:
        return normalize_sku(value)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "category")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("product_url")
    @classmethod
    def clean_url(cls, value: str | None) -> str | None:
        return validate_product_url(value)


class ProductUpdateRequest(BaseModel):
    product_sku: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    category: str | None = Field(default=None, max_length=120)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    price: Money | None = None
    product_url: str | None = Field(default=None, max_length=2048)

    @field_validator("product_sku")
    @classmethod
    def clean_sku(cls, value: str | None) -> str | None:
        return normalize_sku(value)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("description", "category")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("product_url")
    @classmethod
    def clean_url(cls, value: str | None) -> str | None:
        return validate_product_url(value)


class VariantCreateRequest(BaseModel):
    variant_sku: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=160)
    color: str | None = Field(default=None, max_length=80)
    size: str | None = Field(default=None, max_length=80)
    price_override: Money | None = None
    stock_quantity: int | None = Field(default=None, ge=0)

    @field_validator("variant_sku")
    @classmethod
    def clean_sku(cls, value: str | None) -> str | None:
        return normalize_sku(value)

    @field_validator("name", "color", "size")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class VariantUpdateRequest(VariantCreateRequest):
    pass


class SizeGuideRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: dict[str, JsonValue]

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_content(self) -> "SizeGuideRequest":
        if not self.content:
            raise ValueError("Size guide content cannot be empty")
        if len(json.dumps(self.content, ensure_ascii=False).encode()) > 50_000:
            raise ValueError("Size guide content is too large")
        return self


class VariantResponse(BaseModel):
    id: int
    variant_sku: str | None
    name: str | None
    color: str | None
    size: str | None
    price_override: Decimal | None
    effective_price: Decimal | None
    stock_quantity: int | None
    status: CatalogStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer("price_override", "effective_price", when_used="json")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return format(value, ".2f") if value is not None else None


class SizeGuideResponse(BaseModel):
    id: int
    title: str
    content: dict[str, JsonValue]
    updated_at: datetime


class ImageResponse(BaseModel):
    id: int
    variant_id: int | None
    original_filename: str
    content_type: str
    byte_size: int
    width: int
    height: int
    alt_text: str | None
    sort_order: int
    status: Literal["uploading", "active", "cleanup_pending", "deleted"]
    cleanup_attempts: int
    created_at: datetime


class ImageUrlResponse(BaseModel):
    url: str
    expires_in: int


class CleanupResponse(BaseModel):
    image_id: int
    status: Literal["deleted", "cleanup_pending"]
    message: str


class ProductSummaryResponse(BaseModel):
    id: int
    product_sku: str | None
    name: str
    category: str | None
    currency: str
    price: Decimal | None
    status: CatalogStatus
    variant_count: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("price", when_used="json")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return format(value, ".2f") if value is not None else None


class ProductDetailResponse(ProductSummaryResponse):
    description: str | None
    product_url: str | None
    variants: list[VariantResponse]
    size_guide: SizeGuideResponse | None
    images: list[ImageResponse]


class ProductListResponse(BaseModel):
    items: list[ProductSummaryResponse]
    next_cursor: str | None


class ImportErrorResponse(BaseModel):
    row: int | None
    column: str | None
    code: str
    message: str


class ImportPreviewResponse(BaseModel):
    payload_sha256: str
    product_count: int
    variant_count: int
    errors: list[ImportErrorResponse]


class ImportCommitResponse(BaseModel):
    import_id: int
    status: Literal["completed"]
    product_count: int
    variant_count: int
    payload_sha256: str
    replayed: bool = False
