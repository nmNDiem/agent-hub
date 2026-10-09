import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agent_hub_api.channels.contracts import (
    NormalizedAttachment,
    NormalizedInboundMessage,
    VerifiedInboundEvent,
)


class FacebookWebhookError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class FacebookDeliveryReceipt:
    external_account_id: str
    external_thread_id: str
    external_message_ids: tuple[str, ...]
    delivered_at: datetime


@dataclass(frozen=True, slots=True)
class FacebookWebhookBatch:
    messages: tuple[VerifiedInboundEvent, ...]
    delivery_receipts: tuple[FacebookDeliveryReceipt, ...]


class FacebookWebhookAdapter:
    provider = "facebook"

    def __init__(self, app_secret: str) -> None:
        self.app_secret = app_secret.encode()

    def verify_and_normalize(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> tuple[VerifiedInboundEvent, ...]:
        return self.verify_and_parse(raw_body=raw_body, headers=headers).messages

    def verify_and_parse(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> FacebookWebhookBatch:
        signature = headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(self.app_secret, raw_body, hashlib.sha256).hexdigest()
        if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
            raise FacebookWebhookError("FACEBOOK_SIGNATURE_INVALID")
        try:
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID") from exc
        if not isinstance(payload, dict) or payload.get("object") != "page":
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        entries = payload.get("entry")
        if not isinstance(entries, list) or len(entries) > 100:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")

        normalized: list[VerifiedInboundEvent] = []
        receipts: list[FacebookDeliveryReceipt] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
            page_id = self._bounded_string(entry.get("id"), maximum=255)
            messaging = entry.get("messaging", [])
            if not isinstance(messaging, list) or len(messaging) > 100:
                raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
            for item in messaging:
                event = self._normalize_item(page_id, item)
                if event is not None:
                    normalized.append(event)
                receipt = self._normalize_delivery(page_id, item)
                if receipt is not None:
                    receipts.append(receipt)
        return FacebookWebhookBatch(messages=tuple(normalized), delivery_receipts=tuple(receipts))

    def _normalize_item(self, page_id: str, item: object) -> VerifiedInboundEvent | None:
        if not isinstance(item, dict):
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        message = item.get("message")
        if not isinstance(message, dict):
            return None
        if message.get("is_echo") is True:
            return None
        text_value = message.get("text")
        if text_value is None:
            text_value = ""
        if not isinstance(text_value, str) or len(text_value) > 8_000:
            return None
        sender = item.get("sender")
        recipient = item.get("recipient")
        if not isinstance(sender, dict) or not isinstance(recipient, dict):
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        sender_id = self._bounded_string(sender.get("id"), maximum=500)
        recipient_id = self._bounded_string(recipient.get("id"), maximum=255)
        if recipient_id != page_id:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        message_id = self._bounded_string(message.get("mid"), maximum=255)
        attachments = self._attachments(message_id, message.get("attachments"))
        if not text_value.strip() and not attachments:
            return None
        occurred_at = self._occurred_at(item.get("timestamp"))
        canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return VerifiedInboundEvent(
            provider="facebook",
            external_account_id=page_id,
            external_event_id=message_id,
            payload_fingerprint=hashlib.sha256(canonical.encode()).hexdigest(),
            message=NormalizedInboundMessage(
                external_message_id=message_id,
                external_thread_id=sender_id,
                text=text_value,
                occurred_at=occurred_at,
                attachments=attachments,
            ),
        )

    def _attachments(self, message_id: str, value: object) -> tuple[NormalizedAttachment, ...]:
        if value is None:
            return ()
        if not isinstance(value, list) or len(value) > 10:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        normalized: list[NormalizedAttachment] = []
        for index, attachment in enumerate(value):
            if not isinstance(attachment, dict):
                raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
            raw_kind = attachment.get("type")
            if raw_kind not in {"image", "audio", "video", "file"}:
                continue
            payload = attachment.get("payload")
            if not isinstance(payload, dict):
                raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
            source_url: str | None = None
            if raw_kind == "image":
                source_url = self._bounded_string(payload.get("url"), maximum=2_000)
                if not source_url.startswith("https://"):
                    raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
            normalized.append(
                NormalizedAttachment(
                    kind=raw_kind,
                    provider_media_id=f"{message_id}:{index}",
                    source_url=source_url,
                )
            )
        return tuple(normalized)

    def _normalize_delivery(self, page_id: str, item: object) -> FacebookDeliveryReceipt | None:
        if not isinstance(item, dict):
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        delivery = item.get("delivery")
        if not isinstance(delivery, dict):
            return None
        sender = item.get("sender")
        recipient = item.get("recipient")
        if not isinstance(sender, dict) or not isinstance(recipient, dict):
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        external_thread_id = self._bounded_string(sender.get("id"), maximum=500)
        recipient_id = self._bounded_string(recipient.get("id"), maximum=255)
        if recipient_id != page_id:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        mids = delivery.get("mids")
        if not isinstance(mids, list) or not mids or len(mids) > 100:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        external_message_ids = tuple(
            self._bounded_string(message_id, maximum=500) for message_id in mids
        )
        delivered_at = self._occurred_at(delivery.get("watermark"))
        if delivered_at is None:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        return FacebookDeliveryReceipt(
            external_account_id=page_id,
            external_thread_id=external_thread_id,
            external_message_ids=tuple(dict.fromkeys(external_message_ids)),
            delivered_at=delivered_at,
        )

    @staticmethod
    def _bounded_string(value: Any, *, maximum: int) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        return value

    @staticmethod
    def _occurred_at(value: object) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, int) or value < 0:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        try:
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID") from exc
