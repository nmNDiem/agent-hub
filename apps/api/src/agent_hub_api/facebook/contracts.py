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


class FacebookProviderError(RuntimeError):
    pass
