import asyncio
import json
from uuid import UUID

import httpx
import pytest

from agent_hub_api.channels.contracts import (
    DeliveryRequest,
    ProviderDeliveryError,
    RenderedOutboundMessage,
)
from agent_hub_api.channels.vault import CredentialVaultError
from agent_hub_api.facebook.contracts import (
    FacebookPageIdentity,
    FacebookProviderError,
    FacebookSendError,
)
from agent_hub_api.facebook.graph import HttpFacebookGraphGateway
from agent_hub_api.facebook.outbound import FacebookOutboundAdapter


class MissingCredentialVault:
    async def store(self, *, workspace_id: UUID, plaintext: str) -> str:
        raise AssertionError("store must not be called")

    async def resolve(self, credential_ref: str) -> str:
        raise CredentialVaultError("CREDENTIAL_NOT_FOUND")

    async def revoke(self, credential_ref: str) -> None:
        raise AssertionError("revoke must not be called")


class UnexpectedGraphGateway:
    async def validate_page_token(self, page_access_token: str) -> FacebookPageIdentity:
        raise AssertionError("validate_page_token must not be called")

    async def subscribe_page(self, page_id: str, page_access_token: str) -> None:
        raise AssertionError("subscribe_page must not be called")

    async def unsubscribe_page(self, page_id: str, page_access_token: str) -> None:
        raise AssertionError("unsubscribe_page must not be called")

    async def send_text(
        self,
        *,
        page_id: str,
        recipient_id: str,
        text: str,
        page_access_token: str,
    ) -> str:
        raise AssertionError("send_text must not be called")


def test_graph_validates_token_app_permissions_expiry_and_page_task() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path.endswith("/me"):
            return httpx.Response(
                200,
                json={"id": "page-1", "name": "Example Page", "tasks": ["MESSAGE"]},
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "is_valid": True,
                    "app_id": "123456",
                    "expires_at": 4_000_000_000,
                    "data_access_expires_at": 4_000_000_000,
                    "scopes": ["pages_messaging"],
                    "granular_scopes": [],
                }
            },
        )

    gateway = HttpFacebookGraphGateway(
        api_version="v99.0",
        timeout_seconds=5,
        app_id="123456",
        app_secret="secret-app-token",
        transport=httpx.MockTransport(handler),
    )
    identity = asyncio.run(gateway.validate_page_token("secret-page-token"))
    assert identity.page_id == "page-1"
    assert identity.permissions == frozenset({"pages_messaging"})
    assert identity.tasks == frozenset({"MESSAGE"})
    assert len(captured) == 2
    assert captured[0].headers["authorization"] == "Bearer secret-page-token"
    assert captured[1].headers["authorization"] == "Bearer 123456|secret-app-token"


@pytest.mark.parametrize(
    ("tasks", "debug_data", "safe_code"),
    [
        (["MESSAGE"], {"is_valid": False, "app_id": "123456"}, "FACEBOOK_REAUTH_REQUIRED"),
        (
            ["MESSAGE"],
            {"is_valid": True, "app_id": "other", "scopes": ["pages_messaging"]},
            "FACEBOOK_APP_MISMATCH",
        ),
        (
            ["MESSAGE"],
            {"is_valid": True, "app_id": "123456", "scopes": []},
            "FACEBOOK_PERMISSION_EXPIRED",
        ),
        (
            [],
            {"is_valid": True, "app_id": "123456", "scopes": ["pages_messaging"]},
            "FACEBOOK_PERMISSION_EXPIRED",
        ),
        (
            ["MESSAGE"],
            {
                "is_valid": True,
                "app_id": "123456",
                "scopes": ["pages_messaging"],
                "expires_at": 1,
            },
            "FACEBOOK_PERMISSION_EXPIRED",
        ),
    ],
)
def test_graph_rejects_invalid_token_policy(
    tasks: list[str], debug_data: dict[str, object], safe_code: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/me"):
            return httpx.Response(
                200,
                json={"id": "page-1", "name": "Example Page", "tasks": tasks},
            )
        return httpx.Response(200, json={"data": debug_data})

    gateway = HttpFacebookGraphGateway(
        api_version="v99.0",
        timeout_seconds=5,
        app_id="123456",
        app_secret="secret-app-token",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(FacebookProviderError, match=safe_code):
        asyncio.run(gateway.validate_page_token("secret-page-token"))


def test_graph_send_text_uses_bearer_auth_and_official_response_contract() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"recipient_id": "psid-1", "message_id": "mid-1"})

    gateway = HttpFacebookGraphGateway(
        api_version="v99.0",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    async def scenario() -> None:
        result = await gateway.send_text(
            page_id="page-1",
            recipient_id="psid-1",
            text="Xin chào",
            page_access_token="secret-page-token",
        )
        assert result == "mid-1"

    asyncio.run(scenario())
    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert request.url == httpx.URL("https://graph.facebook.com/v99.0/page-1/messages")
    assert request.headers["authorization"] == "Bearer secret-page-token"
    assert "secret-page-token" not in str(request.url)
    assert json.loads(request.content) == {
        "recipient": {"id": "psid-1"},
        "messaging_type": "RESPONSE",
        "message": {"text": "Xin chào"},
    }


@pytest.mark.parametrize(
    ("status_code", "payload", "safe_code", "retryable"),
    [
        (
            503,
            {"error": {"code": 2, "is_transient": True}},
            "FACEBOOK_DELIVERY_UNKNOWN",
            False,
        ),
        (429, {"error": {"code": 4}}, "FACEBOOK_UNAVAILABLE", True),
        (400, {"error": {"code": 190}}, "FACEBOOK_REAUTH_REQUIRED", False),
        (400, {"error": {"code": 100}}, "FACEBOOK_SEND_REJECTED", False),
    ],
)
def test_graph_send_text_maps_provider_errors_without_exposing_payload(
    status_code: int,
    payload: dict[str, object],
    safe_code: str,
    retryable: bool,
) -> None:
    gateway = HttpFacebookGraphGateway(
        api_version="v99.0",
        timeout_seconds=5,
        transport=httpx.MockTransport(lambda _: httpx.Response(status_code, json=payload)),
    )

    async def scenario() -> None:
        with pytest.raises(FacebookSendError) as captured:
            await gateway.send_text(
                page_id="page-1",
                recipient_id="psid-1",
                text="Hello",
                page_access_token="secret-page-token",
            )
        assert captured.value.safe_code == safe_code
        assert captured.value.retryable is retryable
        assert str(captured.value) == safe_code

    asyncio.run(scenario())


def test_graph_send_text_does_not_retry_ambiguous_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("response lost", request=request)

    gateway = HttpFacebookGraphGateway(
        api_version="v99.0",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    async def scenario() -> None:
        with pytest.raises(FacebookSendError) as captured:
            await gateway.send_text(
                page_id="page-1",
                recipient_id="psid-1",
                text="Hello",
                page_access_token="secret-page-token",
            )
        assert captured.value.safe_code == "FACEBOOK_DELIVERY_UNKNOWN"
        assert captured.value.retryable is False

    asyncio.run(scenario())


def test_graph_send_text_does_not_retry_malformed_success_response() -> None:
    gateway = HttpFacebookGraphGateway(
        api_version="v99.0",
        timeout_seconds=5,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )

    async def scenario() -> None:
        with pytest.raises(FacebookSendError) as captured:
            await gateway.send_text(
                page_id="page-1",
                recipient_id="psid-1",
                text="Hello",
                page_access_token="secret-page-token",
            )
        assert captured.value.safe_code == "FACEBOOK_DELIVERY_UNKNOWN"
        assert captured.value.retryable is False

    asyncio.run(scenario())


def test_outbound_adapter_terminalizes_missing_page_credential() -> None:
    adapter = FacebookOutboundAdapter(
        vault=MissingCredentialVault(),
        graph=UnexpectedGraphGateway(),
    )
    request = DeliveryRequest(
        delivery_id=1,
        provider="facebook",
        external_account_id="page-1",
        credential_ref="supabase-vault:missing",
        external_thread_id="psid-1",
        idempotency_key="message-1",
        message=RenderedOutboundMessage(text="Hello"),
    )

    async def scenario() -> None:
        with pytest.raises(ProviderDeliveryError) as captured:
            await adapter.deliver(request)
        assert captured.value.safe_code == "FACEBOOK_REAUTH_REQUIRED"
        assert captured.value.retryable is False

    asyncio.run(scenario())
