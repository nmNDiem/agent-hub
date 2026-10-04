from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
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


def normalize_handoff_url(value: str) -> str:
    candidate = value.strip()
    if any(ord(character) < 32 for character in candidate):
        raise ValueError("Contact URL cannot contain control characters")
    parsed = urlsplit(candidate)
    if parsed.scheme == "https" and parsed.hostname:
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("HTTPS contact URL cannot contain credentials or a fragment")
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("HTTPS contact URL port is invalid") from exc
        return candidate
    if parsed.scheme == "mailto" and parsed.path and not parsed.query and not parsed.fragment:
        try:
            normalized_email = validate_email(
                parsed.path, check_deliverability=False
            ).normalized
        except EmailNotValidError as exc:
            raise ValueError("Mail contact URL is invalid") from exc
        return f"mailto:{normalized_email}"
    if parsed.scheme == "tel" and parsed.path and not parsed.query and not parsed.fragment:
        allowed = set("+0123456789()-. ")
        digits = sum(character.isdigit() for character in parsed.path)
        if any(character not in allowed for character in parsed.path) or not 7 <= digits <= 15:
            raise ValueError("Phone contact URL is invalid")
        return candidate
    raise ValueError("Contact URL must use HTTPS, mailto, or tel")


class WidgetConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=160)
    greeting: str | None = Field(default=None, max_length=2_000)
    brand_color: str = Field(default="#0F8F87", pattern=r"^#[0-9A-Fa-f]{6}$")
    launcher_position: Literal["left", "right"] = "right"
    allowed_origins: list[str] = Field(default_factory=list, max_length=50)
    handoff_url: str | None = Field(default=None, max_length=500)
    handoff_label: str | None = Field(default=None, max_length=80)

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

    @field_validator("handoff_url")
    @classmethod
    def clean_handoff_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_handoff_url(value)

    @field_validator("handoff_label")
    @classmethod
    def clean_handoff_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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
    handoff_url: str | None
    handoff_label: str | None
    enabled: bool
    draft_differs: bool
    readiness: WidgetReadiness
    active_revision: PublishedRevisionResponse | None
    embed_snippet: str | None
