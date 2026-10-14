import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from agent_hub_api.channels.contracts import (
    NormalizedAttachment,
    NormalizedInboundMessage,
    VerifiedInboundEvent,
)


class ZaloWebhookError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def extract_oa_id(raw_body: bytes, *, app_id: str) -> str:
    payload = _payload(raw_body)
    if str(payload.get("app_id", "")) != app_id:
        raise ZaloWebhookError("ZALO_APP_MISMATCH")
    recipient = payload.get("recipient")
    oa_id = recipient.get("id") if isinstance(recipient, dict) else None
    if not isinstance(oa_id, str) or not oa_id or len(oa_id) > 255:
        raise ZaloWebhookError("ZALO_OA_ID_INVALID")
    return oa_id


class ZaloWebhookAdapter:
    def __init__(self, *, app_id: str, webhook_secret: str) -> None:
        self.app_id = app_id
        self.webhook_secret = webhook_secret

    def verify_and_normalize(
        self, *, raw_body: bytes, headers: dict[str, str]
    ) -> tuple[VerifiedInboundEvent, ...]:
        payload = _payload(raw_body)
        if str(payload.get("app_id", "")) != self.app_id:
            raise ZaloWebhookError("ZALO_APP_MISMATCH")
        raw_timestamp = payload.get("timestamp")
        if not isinstance(raw_timestamp, (str, int)):
            raise ZaloWebhookError("ZALO_TIMESTAMP_INVALID")
        timestamp = str(raw_timestamp)
        signature = headers.get("x-zevent-signature", "")
        expected = hashlib.sha256(
            self.app_id.encode() + raw_body + timestamp.encode() + self.webhook_secret.encode()
        ).hexdigest()
        supplied = signature.removeprefix("sha256=")
        if len(supplied) != len(expected) or not hmac.compare_digest(supplied, expected):
            raise ZaloWebhookError("ZALO_SIGNATURE_INVALID")

        event_name = payload.get("event_name")
        supported = {
            "user_send_text",
            "user_send_image",
            "user_send_audio",
            "user_send_video",
            "user_send_file",
            "user_send_sticker",
            "user_send_link",
        }
        if event_name not in supported:
            return ()
        sender = payload.get("sender")
        recipient = payload.get("recipient")
        message = payload.get("message")
        thread_id = sender.get("id") if isinstance(sender, dict) else None
        oa_id = recipient.get("id") if isinstance(recipient, dict) else None
        if not isinstance(message, dict):
            raise ZaloWebhookError("ZALO_MESSAGE_INVALID")
        message_id = message.get("msg_id")
        if not all(isinstance(value, str) and value for value in (thread_id, oa_id, message_id)):
            raise ZaloWebhookError("ZALO_MESSAGE_INVALID")
        assert isinstance(thread_id, str)
        assert isinstance(oa_id, str)
        assert isinstance(message_id, str)
        text = message.get("text", "")
        if not isinstance(text, str):
            raise ZaloWebhookError("ZALO_MESSAGE_INVALID")
        attachments = self._attachments(event_name, message)
        if event_name == "user_send_link":
            link_text = self._link_text(message)
            text = "\n".join(item for item in (text.strip(), link_text) if item)
        occurred_at = self._occurred_at(raw_timestamp)
        fingerprint = hashlib.sha256(raw_body).hexdigest()
        try:
            normalized = NormalizedInboundMessage(
                external_message_id=message_id,
                external_thread_id=thread_id,
                text=text,
                occurred_at=occurred_at,
                attachments=attachments,
            )
            return (
                VerifiedInboundEvent(
                    provider="zalo",
                    external_account_id=oa_id,
                    external_event_id=message_id,
                    payload_fingerprint=fingerprint,
                    message=normalized,
                ),
            )
        except ValueError as exc:
            raise ZaloWebhookError("ZALO_MESSAGE_INVALID") from exc

    @staticmethod
    def _attachments(
        event_name: object, message: dict[str, Any]
    ) -> tuple[NormalizedAttachment, ...]:
        raw_items = message.get("attachments", [])
        if not isinstance(raw_items, list):
            raise ZaloWebhookError("ZALO_MESSAGE_INVALID")
        result: list[NormalizedAttachment] = []
        for index, item in enumerate(raw_items[:10]):
            if not isinstance(item, dict):
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            raw_kind = item.get("type")
            if event_name == "user_send_sticker":
                raw_kind = "image"
            kind = raw_kind if raw_kind in {"image", "audio", "video", "file"} else None
            if kind is None:
                continue
            source_url = payload.get("url") or payload.get("thumbnail")
            if not isinstance(source_url, str) or not source_url.startswith("https://"):
                source_url = None
            media_id = (
                payload.get("id") or payload.get("token") or f"{message.get('msg_id')}:{index}"
            )
            if not isinstance(media_id, (str, int)):
                continue
            result.append(
                NormalizedAttachment(
                    kind=kind,
                    provider_media_id=str(media_id),
                    source_url=source_url,
                )
            )
        return tuple(result)

    @staticmethod
    def _link_text(message: dict[str, Any]) -> str:
        attachments = message.get("attachments", [])
        if not isinstance(attachments, list):
            return ""
        for item in attachments:
            if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
                continue
            payload = item["payload"]
            url = payload.get("url")
            title = payload.get("title")
            safe_url = url if isinstance(url, str) and url.startswith("https://") else ""
            safe_title = title.strip()[:500] if isinstance(title, str) else ""
            return " — ".join(value for value in (safe_title, safe_url) if value)
        return ""

    @staticmethod
    def _occurred_at(value: str | int) -> datetime:
        try:
            numeric = int(value)
            if numeric > 10_000_000_000:
                numeric //= 1_000
            return datetime.fromtimestamp(numeric, tz=UTC)
        except (OverflowError, OSError, TypeError, ValueError) as exc:
            raise ZaloWebhookError("ZALO_TIMESTAMP_INVALID") from exc


def _payload(raw_body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ZaloWebhookError("ZALO_PAYLOAD_INVALID") from exc
    if not isinstance(value, dict):
        raise ZaloWebhookError("ZALO_PAYLOAD_INVALID")
    return value
