import json
from datetime import UTC, datetime

from agent_hub_api.zalo.contracts import ZaloCredentialBundle


class ZaloCredentialError(RuntimeError):
    pass


def encode_bundle(bundle: ZaloCredentialBundle) -> str:
    return json.dumps(
        {
            "version": 1,
            "access_token": bundle.access_token,
            "refresh_token": bundle.refresh_token,
            "expires_at": bundle.expires_at.astimezone(UTC).isoformat(),
            "webhook_secret": bundle.webhook_secret,
        },
        separators=(",", ":"),
    )


def decode_bundle(value: str) -> ZaloCredentialBundle:
    try:
        payload = json.loads(value)
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError
        access_token = payload["access_token"]
        refresh_token = payload["refresh_token"]
        expires_at = datetime.fromisoformat(payload["expires_at"])
        webhook_secret = payload.get("webhook_secret")
        if (
            not isinstance(access_token, str)
            or not access_token
            or len(access_token) > 8_192
            or not isinstance(refresh_token, str)
            or not refresh_token
            or len(refresh_token) > 8_192
            or expires_at.tzinfo is None
            or (webhook_secret is not None and not isinstance(webhook_secret, str))
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ZaloCredentialError("ZALO_CREDENTIAL_INVALID") from exc
    return ZaloCredentialBundle(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        webhook_secret=webhook_secret,
    )
