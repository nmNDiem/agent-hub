from typing import Any

import httpx

from agent_hub_api.zalo.contracts import (
    ZaloGateway,
    ZaloOAIdentity,
    ZaloProviderError,
    ZaloTokenSet,
)


class HttpZaloGateway(ZaloGateway):
    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        timeout_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def exchange_code(self, *, code: str, code_verifier: str) -> ZaloTokenSet:
        return await self._token_request(
            {
                "code": code,
                "app_id": self.app_id,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            }
        )

    async def refresh_token(self, refresh_token: str) -> ZaloTokenSet:
        return await self._token_request(
            {"refresh_token": refresh_token, "app_id": self.app_id, "grant_type": "refresh_token"}
        )

    async def _token_request(self, data: dict[str, str]) -> ZaloTokenSet:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.post(
                    "https://oauth.zaloapp.com/v4/oa/access_token",
                    headers={"secret_key": self.app_secret},
                    data=data,
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ZaloProviderError("ZALO_OAUTH_UNAVAILABLE", retryable=True) from exc
        if response.is_error:
            raise self._provider_error(response, auth=True)
        payload = self._json_object(response, "ZALO_TOKEN_INVALID")
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        raw_expires = payload.get("expires_in")
        if not isinstance(raw_expires, (str, int)) or isinstance(raw_expires, bool):
            raise ZaloProviderError("ZALO_TOKEN_INVALID")
        try:
            expires_in = int(raw_expires)
        except (TypeError, ValueError) as exc:
            raise ZaloProviderError("ZALO_TOKEN_INVALID") from exc
        if (
            not isinstance(access_token, str)
            or not access_token
            or len(access_token) > 8_192
            or not isinstance(refresh_token, str)
            or not refresh_token
            or len(refresh_token) > 8_192
            or not 60 <= expires_in <= 172_800
        ):
            raise ZaloProviderError("ZALO_TOKEN_INVALID")
        return ZaloTokenSet(access_token, refresh_token, expires_in)

    async def get_oa(self, access_token: str) -> ZaloOAIdentity:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.get(
                    "https://openapi.zalo.me/v2.0/oa/getoa",
                    headers={"access_token": access_token},
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ZaloProviderError("ZALO_API_UNAVAILABLE", retryable=True) from exc
        if response.is_error:
            raise self._provider_error(response, auth=True)
        payload = self._json_object(response, "ZALO_OA_INVALID")
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ZaloProviderError("ZALO_OA_INVALID")
        oa_id = data.get("oa_id") or data.get("id")
        name = data.get("name")
        if (
            not isinstance(oa_id, str)
            or not oa_id
            or len(oa_id) > 255
            or not isinstance(name, str)
            or not name.strip()
            or len(name.strip()) > 160
        ):
            raise ZaloProviderError("ZALO_OA_INVALID")
        return ZaloOAIdentity(oa_id=oa_id, name=name.strip())

    async def send_text(self, *, recipient_id: str, text: str, access_token: str) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self.transport
            ) as client:
                response = await client.post(
                    "https://openapi.zalo.me/v3.0/oa/message/cs",
                    headers={"access_token": access_token},
                    json={"recipient": {"user_id": recipient_id}, "message": {"text": text}},
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ZaloProviderError("ZALO_DELIVERY_UNKNOWN") from exc
        if response.is_error:
            raise self._provider_error(response, auth=False)
        payload = self._json_object(response, "ZALO_DELIVERY_UNKNOWN")
        data = payload.get("data")
        message_id = data.get("message_id") if isinstance(data, dict) else None
        if not isinstance(message_id, str) or not message_id or len(message_id) > 500:
            raise ZaloProviderError("ZALO_DELIVERY_UNKNOWN")
        return message_id

    @staticmethod
    def _json_object(response: httpx.Response, safe_code: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ZaloProviderError(safe_code) from exc
        if not isinstance(payload, dict):
            raise ZaloProviderError(safe_code)
        raw_error = payload.get("error")
        if raw_error not in {None, 0, "0"}:
            raise ZaloProviderError(safe_code)
        return payload

    @staticmethod
    def _provider_error(response: httpx.Response, *, auth: bool) -> ZaloProviderError:
        if response.status_code in {401, 403}:
            return ZaloProviderError("ZALO_REAUTH_REQUIRED")
        if response.status_code == 429:
            return ZaloProviderError("ZALO_RATE_LIMITED", retryable=True)
        if response.status_code >= 500:
            return ZaloProviderError(
                "ZALO_OAUTH_UNAVAILABLE" if auth else "ZALO_UNAVAILABLE", retryable=True
            )
        return ZaloProviderError("ZALO_AUTH_REJECTED" if auth else "ZALO_SEND_REJECTED")
