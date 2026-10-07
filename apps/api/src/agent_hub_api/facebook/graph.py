import httpx

from agent_hub_api.facebook.contracts import (
    FacebookGraphGateway,
    FacebookPageIdentity,
    FacebookProviderError,
)


class HttpFacebookGraphGateway(FacebookGraphGateway):
    def __init__(self, *, api_version: str, timeout_seconds: int) -> None:
        self.api_version = api_version
        self.timeout_seconds = timeout_seconds

    async def validate_page_token(self, page_access_token: str) -> FacebookPageIdentity:
        try:
            async with httpx.AsyncClient(
                base_url=f"https://graph.facebook.com/{self.api_version}",
                timeout=self.timeout_seconds,
            ) as client:
                response = await client.get(
                    "/me",
                    params={"fields": "id,name"},
                    headers={"Authorization": f"Bearer {page_access_token}"},
                )
            response.raise_for_status()
            payload = response.json()
            page_id = payload.get("id")
            name = payload.get("name")
            if not isinstance(page_id, str) or not page_id or len(page_id) > 255:
                raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
            if not isinstance(name, str) or not name.strip() or len(name) > 160:
                raise FacebookProviderError("FACEBOOK_TOKEN_INVALID")
            return FacebookPageIdentity(page_id=page_id, name=name.strip())
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise FacebookProviderError("FACEBOOK_TOKEN_INVALID") from exc

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
