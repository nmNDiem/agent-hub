import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from agent_hub_api.channels.contracts import NormalizedInboundMessage, VerifiedInboundEvent


class FacebookWebhookError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class FacebookWebhookAdapter:
    provider = "facebook"

    def __init__(self, app_secret: str) -> None:
        self.app_secret = app_secret.encode()

    def verify_and_normalize(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> tuple[VerifiedInboundEvent, ...]:
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
        return tuple(normalized)

    def _normalize_item(
        self, page_id: str, item: object
    ) -> VerifiedInboundEvent | None:
        if not isinstance(item, dict):
            raise FacebookWebhookError("FACEBOOK_PAYLOAD_INVALID")
        message = item.get("message")
        if not isinstance(message, dict):
            return None
        if message.get("is_echo") is True or "attachments" in message:
            return None
        text_value = message.get("text")
        if (
            not isinstance(text_value, str)
            or not text_value.strip()
            or len(text_value) > 8_000
        ):
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
            ),
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
