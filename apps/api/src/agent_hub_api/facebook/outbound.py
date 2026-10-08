from agent_hub_api.channels.contracts import (
    CredentialVault,
    DeliveryRequest,
    OutboundAdapter,
    ProviderDeliveryError,
    ProviderDeliveryResult,
)
from agent_hub_api.channels.vault import CredentialVaultError
from agent_hub_api.facebook.contracts import FacebookGraphGateway, FacebookSendError


class FacebookOutboundAdapter(OutboundAdapter):
    provider = "facebook"

    def __init__(self, *, vault: CredentialVault, graph: FacebookGraphGateway) -> None:
        self.vault = vault
        self.graph = graph

    async def deliver(self, request: DeliveryRequest) -> ProviderDeliveryResult:
        if request.provider != "facebook":
            raise ProviderDeliveryError("FACEBOOK_PROVIDER_MISMATCH", retryable=False)
        if request.external_account_id is None or request.credential_ref is None:
            raise ProviderDeliveryError("FACEBOOK_REAUTH_REQUIRED", retryable=False)
        if len(request.message.text) > 2_000:
            raise ProviderDeliveryError("FACEBOOK_TEXT_TOO_LONG", retryable=False)
        try:
            page_access_token = await self.vault.resolve(request.credential_ref)
        except CredentialVaultError as exc:
            retryable = str(exc) == "CREDENTIAL_RESOLVE_FAILED"
            safe_code = "CREDENTIAL_VAULT_UNAVAILABLE" if retryable else "FACEBOOK_REAUTH_REQUIRED"
            raise ProviderDeliveryError(safe_code, retryable=retryable) from exc
        try:
            external_message_id = await self.graph.send_text(
                page_id=request.external_account_id,
                recipient_id=request.external_thread_id,
                text=request.message.text,
                page_access_token=page_access_token,
            )
        except FacebookSendError as exc:
            raise ProviderDeliveryError(exc.safe_code, retryable=exc.retryable) from exc
        return ProviderDeliveryResult(external_message_id=external_message_id)
