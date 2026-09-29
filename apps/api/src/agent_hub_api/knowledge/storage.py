from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

import httpx


class KnowledgeStorageError(RuntimeError):
    """Private object storage failed without exposing provider details."""


class KnowledgeStorage(Protocol):
    async def upload_file(
        self, *, object_key: str, source: Path, content_type: str
    ) -> None: ...

    async def download_file(
        self, *, object_key: str, destination: Path, max_bytes: int
    ) -> None: ...

    async def delete(self, *, object_key: str) -> None: ...


class UnavailableKnowledgeStorage:
    async def upload_file(self, *, object_key: str, source: Path, content_type: str) -> None:
        raise KnowledgeStorageError("Knowledge storage is not configured")

    async def download_file(
        self, *, object_key: str, destination: Path, max_bytes: int
    ) -> None:
        raise KnowledgeStorageError("Knowledge storage is not configured")

    async def delete(self, *, object_key: str) -> None:
        raise KnowledgeStorageError("Knowledge storage is not configured")


async def _file_chunks(path: Path, *, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
    with path.open("rb") as source:
        while chunk := await asyncio.to_thread(source.read, chunk_size):
            yield chunk


class SupabaseKnowledgeStorage:
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

    async def upload_file(self, *, object_key: str, source: Path, content_type: str) -> None:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    content=_file_chunks(source),
                    headers={
                        **self.headers,
                        "content-type": content_type,
                        # The object key is server-generated and permanently bound to one
                        # content hash, so retrying the same storage saga is safe.
                        "x-upsert": "true",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise KnowledgeStorageError("Unable to store knowledge document") from exc

    async def download_file(
        self, *, object_key: str, destination: Path, max_bytes: int
    ) -> None:
        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}"
        total = 0
        try:
            async with (
                httpx.AsyncClient(timeout=30.0) as client,
                client.stream("GET", url, headers=self.headers) as response,
            ):
                response.raise_for_status()
                with destination.open("wb") as output:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            raise KnowledgeStorageError(
                                "Stored knowledge document exceeds configured size"
                            )
                        await asyncio.to_thread(output.write, chunk)
        except KnowledgeStorageError:
            destination.unlink(missing_ok=True)
            raise
        except (OSError, httpx.HTTPError) as exc:
            destination.unlink(missing_ok=True)
            raise KnowledgeStorageError("Unable to read knowledge document") from exc

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
            raise KnowledgeStorageError("Unable to remove knowledge document") from exc
