from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_widget_origin(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Origin must use HTTP(S)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Origin cannot contain credentials, query data, or a fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("Origin cannot contain a path")
    hostname = parsed.hostname.casefold()
    if parsed.scheme == "http" and hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("HTTP origins are limited to local loopback")
    default_port = 80 if parsed.scheme == "http" else 443
    port = parsed.port
    host = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host if port in {None, default_port} else f"{host}:{port}"
    return urlunsplit((parsed.scheme, netloc, "", "", ""))


class WidgetConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=160)
    greeting: str | None = Field(default=None, max_length=2_000)
    brand_color: str = Field(default="#0F8F87", pattern=r"^#[0-9A-Fa-f]{6}$")
    launcher_position: Literal["left", "right"] = "right"
    allowed_origins: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Display name cannot be blank")
        return cleaned

    @field_validator("greeting")
    @classmethod
    def clean_greeting(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("brand_color")
    @classmethod
    def normalize_brand_color(cls, value: str) -> str:
        return value.upper()

    @field_validator("allowed_origins")
    @classmethod
    def clean_origins(cls, value: list[str]) -> list[str]:
        return sorted({normalize_widget_origin(item) for item in value})


class WidgetReadiness(BaseModel):
    has_allowed_origin: bool
    has_catalog_scope: bool
    has_knowledge: bool
    can_publish: bool


class PublishedRevisionResponse(BaseModel):
    revision_no: int
    published_at: datetime


class WidgetConfigResponse(BaseModel):
    public_agent_id: UUID
    display_name: str
    greeting: str | None
    status: Literal["draft", "published", "paused"]
    brand_color: str
    launcher_position: Literal["left", "right"]
    allowed_origins: list[str]
    enabled: bool
    draft_differs: bool
    readiness: WidgetReadiness
    active_revision: PublishedRevisionResponse | None
    embed_snippet: str | None
