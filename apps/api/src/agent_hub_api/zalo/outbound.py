from agent_hub_api.channels.contracts import (
    DeliveryRequest,
    OutboundAdapter,
    ProviderDeliveryError,
    ProviderDeliveryResult,
)
from agent_hub_api.zalo.contracts import ZaloGateway, ZaloProviderError
from agent_hub_api.zalo.tokens import ZaloTokenError, ZaloTokenManager


class ZaloOutboundAdapter(OutboundAdapter):
    provider = "zalo"

    def __init__(self, *, tokens: ZaloTokenManager, gateway: ZaloGateway) -> None:
        self.tokens = tokens
        self.gateway = gateway

    async def deliver(self, request: DeliveryRequest) -> ProviderDeliveryResult:
        if request.provider != "zalo":
            raise ProviderDeliveryError("ZALO_PROVIDER_MISMATCH", retryable=False)
        if request.external_account_id is None or request.credential_ref is None:
            raise ProviderDeliveryError("ZALO_REAUTH_REQUIRED", retryable=False)
        if len(request.message.text) > 2_000:
            raise ProviderDeliveryError("ZALO_TEXT_TOO_LONG", retryable=False)
        try:
            access_token = await self.tokens.access_token(connection_id=request.connection_id)
            message_id = await self.gateway.send_text(
                recipient_id=request.external_thread_id,
                text=request.message.text,
                access_token=access_token,
            )
        except ZaloTokenError as exc:
            raise ProviderDeliveryError(exc.safe_code, retryable=exc.retryable) from exc
        except ZaloProviderError as exc:
            raise ProviderDeliveryError(exc.safe_code, retryable=exc.retryable) from exc
        return ProviderDeliveryResult(external_message_id=message_id)
