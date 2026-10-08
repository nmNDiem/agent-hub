from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

ChannelProvider = Literal["web", "facebook", "zalo"]
MessageDirection = Literal["inbound", "outbound"]


@dataclass(frozen=True, slots=True)
class ChannelCapabilities:
    text: bool = True
    images: bool = False
    product_cards: bool = False
    source_references: bool = False
    streaming: bool = False


@dataclass(frozen=True, slots=True)
class NormalizedAttachment:
    kind: Literal["image"]
    provider_media_id: str
    content_type: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_media_id or len(self.provider_media_id) > 500:
            raise ValueError("Provider media ID must contain 1 to 500 characters")
        if self.content_type is not None and len(self.content_type) > 100:
            raise ValueError("Attachment content type exceeds 100 characters")


@dataclass(frozen=True, slots=True)
class NormalizedInboundMessage:
    external_message_id: str
    external_thread_id: str
    text: str
    occurred_at: datetime | None = None
    attachments: tuple[NormalizedAttachment, ...] = ()

    def __post_init__(self) -> None:
        if not self.external_message_id or len(self.external_message_id) > 500:
            raise ValueError("External message ID must contain 1 to 500 characters")
        if not self.external_thread_id or len(self.external_thread_id) > 500:
            raise ValueError("External thread ID must contain 1 to 500 characters")
        if len(self.text) > 8_000:
            raise ValueError("Normalized message text exceeds the shared channel limit")
        if not self.text.strip() and not self.attachments:
            raise ValueError("A normalized inbound message must contain text or an attachment")
        if len(self.attachments) > 10:
            raise ValueError("A normalized inbound message supports at most 10 attachments")
        if self.occurred_at is not None and self.occurred_at.tzinfo is None:
            raise ValueError("Provider occurrence time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class VerifiedInboundEvent:
    provider: ChannelProvider
    external_account_id: str
    external_event_id: str
    payload_fingerprint: str
    message: NormalizedInboundMessage

    def __post_init__(self) -> None:
        if not self.external_account_id or len(self.external_account_id) > 255:
            raise ValueError("External account ID must contain 1 to 255 characters")
        if not self.external_event_id or len(self.external_event_id) > 255:
            raise ValueError("External event ID must contain 1 to 255 characters")
        if len(self.payload_fingerprint) != 64:
            raise ValueError("Payload fingerprint must be a SHA-256 hexadecimal digest")
        try:
            int(self.payload_fingerprint, 16)
        except ValueError as exc:
            raise ValueError("Payload fingerprint must be a SHA-256 hexadecimal digest") from exc


@dataclass(frozen=True, slots=True)
class NormalizedOutboundMessage:
    text: str
    product_links: tuple[str, ...] = ()
    source_labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip() or len(self.text) > 8_000:
            raise ValueError("Outbound text must contain 1 to 8000 characters")
        if len(self.product_links) > 20 or len(self.source_labels) > 20:
            raise ValueError("Outbound evidence exceeds the shared channel item limit")
        if any(len(value) > 1_000 for value in self.product_links):
            raise ValueError("Outbound product link exceeds 1000 characters")
        if any(not value.strip() or len(value) > 200 for value in self.source_labels):
            raise ValueError("Outbound source labels must contain 1 to 200 characters")


@dataclass(frozen=True, slots=True)
class RenderedOutboundMessage:
    text: str
    fallback_used: bool = False
    product_links: tuple[str, ...] = ()
    source_labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DeliveryRequest:
    delivery_id: int
    provider: ChannelProvider
    external_account_id: str | None
    credential_ref: str | None
    external_thread_id: str
    idempotency_key: str
    message: RenderedOutboundMessage


@dataclass(frozen=True, slots=True)
class ProviderDeliveryResult:
    external_message_id: str


class WebhookAdapter(Protocol):
    provider: ChannelProvider

    def verify_and_normalize(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> tuple[VerifiedInboundEvent, ...]: ...


class ChannelRenderer(Protocol):
    provider: ChannelProvider
    capabilities: ChannelCapabilities

    def render(self, message: NormalizedOutboundMessage) -> RenderedOutboundMessage: ...


class OutboundAdapter(Protocol):
    provider: ChannelProvider

    async def deliver(self, request: DeliveryRequest) -> ProviderDeliveryResult: ...


class CredentialVault(Protocol):
    async def store(self, *, workspace_id: UUID, plaintext: str) -> str: ...

    async def resolve(self, credential_ref: str) -> str: ...

    async def revoke(self, credential_ref: str) -> None: ...


class ProviderDeliveryError(RuntimeError):
    def __init__(self, safe_code: str, *, retryable: bool) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code
        self.retryable = retryable
