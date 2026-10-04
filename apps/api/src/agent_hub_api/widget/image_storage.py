from __future__ import annotations

from typing import Protocol

import httpx


class VisitorImageStorageError(RuntimeError):
    """Private visitor image storage failed without exposing provider details."""


class VisitorImageStorage(Protocol):
    async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None: ...

    async def download(self, *, object_key: str, max_bytes: int) -> bytes: ...

    async def delete(self, *, object_key: str) -> None: ...


class SupabaseVisitorImageStorage:
    def __init__(self, *, base_url: str, service_key: str, bucket: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key
        self.bucket = bucket

    @property
    def headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }

    async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url,
                    content=content,
                    headers={
                        **self.headers,
                        "content-type": content_type,
                        "x-upsert": "false",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VisitorImageStorageError("Unable to store visitor image") from exc

    async def download(self, *, object_key: str, max_bytes: int) -> bytes:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        chunks: list[bytes] = []
        total = 0
        try:
            async with (
                httpx.AsyncClient(timeout=20.0) as client,
                client.stream("GET", url, headers=self.headers) as response,
            ):
                response.raise_for_status()
                async for chunk in response.aiter_bytes(64 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise VisitorImageStorageError(
                            "Stored visitor image exceeds configured size"
                        )
                    chunks.append(chunk)
        except VisitorImageStorageError:
            raise
        except httpx.HTTPError as exc:
            raise VisitorImageStorageError("Unable to read visitor image") from exc
        return b"".join(chunks)

    async def delete(self, *, object_key: str) -> None:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.request(
                    "DELETE",
                    url,
                    json={"prefixes": [object_key]},
                    headers={**self.headers, "content-type": "application/json"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VisitorImageStorageError("Unable to remove visitor image") from exc
