from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ZaloTokenSet:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class ZaloOAIdentity:
    oa_id: str
    name: str


class ZaloGateway(Protocol):
    async def exchange_code(self, *, code: str, code_verifier: str) -> ZaloTokenSet: ...

    async def refresh_token(self, refresh_token: str) -> ZaloTokenSet: ...

    async def get_oa(self, access_token: str) -> ZaloOAIdentity: ...

    async def send_text(self, *, recipient_id: str, text: str, access_token: str) -> str: ...


class ZaloProviderError(RuntimeError):
    def __init__(self, safe_code: str, *, retryable: bool = False) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ZaloCredentialBundle:
    access_token: str
    refresh_token: str
    expires_at: datetime
    webhook_secret: str | None = None
