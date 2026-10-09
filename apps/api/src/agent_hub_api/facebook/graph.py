from datetime import UTC, datetime

import httpx

from agent_hub_api.facebook.contracts import (
    FacebookGraphGateway,
    FacebookPageIdentity,
    FacebookProviderError,
    FacebookSendError,
)


class HttpFacebookGraphGateway(FacebookGraphGateway):
    def __init__(
        self,
        *,
        api_version: str,
        timeout_seconds: int,
        app_id: str | None = None,
        app_secret: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_version = api_version
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.app_id = app_id
        self.app_secret = app_secret

    async def validate_page_token(self, page_access_token: str) -> FacebookPageIdentity:
        try:
            async with httpx.AsyncClient(
                base_url=f"https://graph.facebook.com/{self.api_version}",
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(
                    "/me",
                    params={"fields": "id,name,tasks"},
                    headers={"Authorization": f"Bearer {page_access_token}"},
                )
                response.raise_for_status()
                payload = response.json()
                debug_payload: object | None = None
                if self.app_id is not None and self.app_secret is not None:
                    debug = await client.get(
                        "/debug_token",
                        params={"input_token": page_access_token},
                        headers={"Authorization": f"Bearer {self.app_id}|{self.app_secret}"},
                    )
                    debug.raise_for_status()
                    debug_payload = debug.json()
            page_id = payload.get("id")
            name = payload.get("name")
            if not isinstance(page_id, str) or not page_id or len(page_id) > 255:
                raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
            if not isinstance(name, str) or not name.strip() or len(name) > 160:
                raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
            raw_tasks = payload.get("tasks", [])
            if not isinstance(raw_tasks, list) or any(
                not isinstance(item, str) for item in raw_tasks
            ):
                raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
            app_id: str | None = None
            expires_at: datetime | None = None
            data_access_expires_at: datetime | None = None
            permissions = frozenset({"pages_messaging"})
            if debug_payload is not None:
                if not isinstance(debug_payload, dict) or not isinstance(
                    debug_payload.get("data"), dict
                ):
                    raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
                data = debug_payload["data"]
                if data.get("is_valid") is not True:
                    raise FacebookProviderError("FACEBOOK_REAUTH_REQUIRED")
                raw_app_id = data.get("app_id")
                if not isinstance(raw_app_id, str) or raw_app_id != self.app_id:
                    raise FacebookProviderError("FACEBOOK_APP_MISMATCH")
                app_id = raw_app_id
                permissions = self._permissions(data)
                expires_at = self._expiry(data.get("expires_at"))
                data_access_expires_at = self._expiry(data.get("data_access_expires_at"))
            if "pages_messaging" not in permissions or "MESSAGE" not in raw_tasks:
                raise FacebookProviderError("FACEBOOK_PERMISSION_EXPIRED")
            now = datetime.now(UTC)
            if (expires_at is not None and expires_at <= now) or (
                data_access_expires_at is not None and data_access_expires_at <= now
            ):
                raise FacebookProviderError("FACEBOOK_PERMISSION_EXPIRED")
            return FacebookPageIdentity(
                page_id=page_id,
                name=name.strip(),
                app_id=app_id,
                expires_at=expires_at,
                data_access_expires_at=data_access_expires_at,
                permissions=permissions,
                tasks=frozenset(raw_tasks),
            )
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise FacebookProviderError("FACEBOOK_TOKEN_INVALID") from exc

    @staticmethod
    def _expiry(value: object) -> datetime | None:
        if value in {None, 0}:
            return None
        if not isinstance(value, int) or value < 0:
            raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise FacebookProviderError("FACEBOOK_TOKEN_INVALID") from exc

    @staticmethod
    def _permissions(data: dict[str, object]) -> frozenset[str]:
        values: set[str] = set()
        scopes = data.get("scopes", [])
        if not isinstance(scopes, list):
            raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
        for scope in scopes:
            if not isinstance(scope, str):
                raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
            values.add(scope)
        granular = data.get("granular_scopes", [])
        if not isinstance(granular, list):
            raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
        for item in granular:
            if isinstance(item, dict) and isinstance(item.get("scope"), str):
                values.add(item["scope"])
        return frozenset(values)

    async def subscribe_page(self, page_id: str, page_access_token: str) -> None:
        await self._subscription_request(
            "POST",
            page_id=page_id,
            page_access_token=page_access_token,
            params={"subscribed_fields": "messages"},
        )

    async def unsubscribe_page(self, page_id: str, page_access_token: str) -> None:
        await self._subscription_request(
            "DELETE",
            page_id=page_id,
            page_access_token=page_access_token,
            params=None,
        )

    async def _subscription_request(
        self,
        method: str,
        *,
        page_id: str,
        page_access_token: str,
        params: dict[str, str] | None,
    ) -> None:
        try:
            async with httpx.AsyncClient(
                base_url=f"https://graph.facebook.com/{self.api_version}",
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    f"/{page_id}/subscribed_apps",
                    params=params,
                    headers={"Authorization": f"Bearer {page_access_token}"},
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("success") is not True:
                raise FacebookProviderError("FACEBOOK_SUBSCRIPTION_FAILED")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise FacebookProviderError("FACEBOOK_SUBSCRIPTION_FAILED") from exc

    async def send_text(
        self,
        *,
        page_id: str,
        recipient_id: str,
        text: str,
        page_access_token: str,
    ) -> str:
        try:
            async with httpx.AsyncClient(
                base_url=f"https://graph.facebook.com/{self.api_version}",
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"/{page_id}/messages",
                    headers={"Authorization": f"Bearer {page_access_token}"},
                    json={
                        "recipient": {"id": recipient_id},
                        "messaging_type": "RESPONSE",
                        "message": {"text": text},
                    },
                )
        except httpx.TimeoutException as exc:
            raise FacebookSendError("FACEBOOK_DELIVERY_UNKNOWN", retryable=False) from exc
        except httpx.TransportError as exc:
            raise FacebookSendError("FACEBOOK_DELIVERY_UNKNOWN", retryable=False) from exc

        if response.is_error:
            raise self._send_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise FacebookSendError("FACEBOOK_DELIVERY_UNKNOWN", retryable=False) from exc
        message_id = payload.get("message_id") if isinstance(payload, dict) else None
        if not isinstance(message_id, str) or not message_id or len(message_id) > 500:
            raise FacebookSendError("FACEBOOK_DELIVERY_UNKNOWN", retryable=False)
        return message_id

    @staticmethod
    def _send_error(response: httpx.Response) -> FacebookSendError:
        provider_code: int | None = None
        is_transient = False
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                raw_code = error.get("code")
                if isinstance(raw_code, int):
                    provider_code = raw_code
                is_transient = error.get("is_transient") is True

        if response.status_code in {401, 403} or provider_code in {10, 190, 200}:
            return FacebookSendError("FACEBOOK_REAUTH_REQUIRED", retryable=False)
        if response.status_code >= 500:
            return FacebookSendError("FACEBOOK_DELIVERY_UNKNOWN", retryable=False)
        if response.status_code == 429 or is_transient:
            return FacebookSendError("FACEBOOK_UNAVAILABLE", retryable=True)
        if provider_code in {1, 2, 4, 17, 32, 341, 613}:
            return FacebookSendError("FACEBOOK_RATE_LIMITED", retryable=True)
        return FacebookSendError("FACEBOOK_SEND_REJECTED", retryable=False)
