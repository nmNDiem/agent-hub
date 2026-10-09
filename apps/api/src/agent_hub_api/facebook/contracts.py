from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FacebookPageIdentity:
    page_id: str
    name: str
    app_id: str | None = None
    expires_at: datetime | None = None
    data_access_expires_at: datetime | None = None
    permissions: frozenset[str] = frozenset({"pages_messaging"})
    tasks: frozenset[str] = frozenset({"MESSAGE"})


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
    def __init__(self, safe_code: str) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code


class FacebookSendError(FacebookProviderError):
    def __init__(self, safe_code: str, *, retryable: bool) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code
        self.retryable = retryable
