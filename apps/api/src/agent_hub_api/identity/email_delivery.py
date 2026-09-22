from typing import Protocol


class EmailDelivery(Protocol):
    async def send_verification(self, *, recipient: str, token: str) -> None: ...

    async def send_password_reset(self, *, recipient: str, token: str) -> None: ...


class UnavailableEmailDelivery:
    async def send_verification(self, *, recipient: str, token: str) -> None:
        raise RuntimeError("Email delivery is not configured")

    async def send_password_reset(self, *, recipient: str, token: str) -> None:
        raise RuntimeError("Email delivery is not configured")
