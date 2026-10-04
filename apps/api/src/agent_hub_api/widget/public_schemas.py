from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class WidgetCapabilities(BaseModel):
    image_input: bool = False


class WidgetPublishedConfig(BaseModel):
    display_name: str
    greeting: str | None
    brand_color: str
    launcher_position: Literal["left", "right"]
    capabilities: WidgetCapabilities


class WidgetSessionResponse(BaseModel):
    access_token: str
    expires_at: datetime
    config: WidgetPublishedConfig


class WidgetConversationResponse(BaseModel):
    public_id: UUID
    status: Literal["open", "deleted"]
    retention_until: datetime


class WidgetMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4_000)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be blank")
        return cleaned


class PublicPriceSummary(BaseModel):
    kind: Literal["exact", "range", "unknown"]
    minimum: str | None
    maximum: str | None


class PublicAvailabilitySummary(BaseModel):
    total_locations: int
    in_stock_locations: int
    out_of_stock_locations: int
    unknown_locations: int


class PublicProductVariant(BaseModel):
    sku: str | None
    name: str | None
    options: dict[str, str]
    attributes: dict[str, JsonValue]
    inventory_state: Literal["in_stock", "out_of_stock", "unknown"]


class PublicProductCard(BaseModel):
    card_id: str
    sku: str | None
    name: str
    product_url: str | None
    currency: str
    price: PublicPriceSummary
    availability: PublicAvailabilitySummary
    options: dict[str, list[str]]
    attributes: dict[str, JsonValue]
    variants: list[PublicProductVariant]
    images: list[JsonValue] = Field(default_factory=list)


class PublicSourceReference(BaseModel):
    source_id: str
    title: str
    locator: str


class PublicGroundedResponse(BaseModel):
    text: str
    product_cards: list[PublicProductCard]
    sources: list[PublicSourceReference]
    usage: dict[str, int]


class WidgetTranscriptMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    status: Literal["pending", "completed", "failed", "cancelled"]
    response_id: UUID | None
    product_cards: list[PublicProductCard] = Field(default_factory=list)
    sources: list[PublicSourceReference] = Field(default_factory=list)
    created_at: datetime


class WidgetTranscriptResponse(BaseModel):
    items: list[WidgetTranscriptMessage]
