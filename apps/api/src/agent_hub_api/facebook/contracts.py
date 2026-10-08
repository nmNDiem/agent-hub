from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FacebookPageIdentity:
    page_id: str
    name: str


class FacebookGraphGateway(Protocol):
    async def validate_page_token(self, page_access_token: str) -> FacebookPageIdentity: ...

    async def subscribe_page(self, page_id: str, page_access_token: str) -> None: ...

    async def unsubscribe_page(self, page_id: str, page_access_token: str) -> None: ...

    async def send_text(
        self,
        *,
        page_id: str,
        recipient_id: str,
        text: str,
        page_access_token: str,
    ) -> str: ...


class FacebookProviderError(RuntimeError):
    pass


class FacebookSendError(FacebookProviderError):
    def __init__(self, safe_code: str, *, retryable: bool) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code
        self.retryable = retryable
