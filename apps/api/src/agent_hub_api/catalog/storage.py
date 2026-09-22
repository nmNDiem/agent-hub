from __future__ import annotations

from typing import Protocol

import httpx


class StorageError(RuntimeError):
    """Storage operation failed without exposing provider credentials or response bodies."""


class CatalogStorage(Protocol):
    async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None: ...

    async def delete(self, *, object_key: str) -> None: ...

    async def create_signed_url(self, *, object_key: str, expires_in: int) -> str: ...


class UnavailableCatalogStorage:
    async def upload(self, *, object_key: str, content: bytes, content_type: str) -> None:
        raise StorageError("Catalog storage is not configured")

    async def delete(self, *, object_key: str) -> None:
        raise StorageError("Catalog storage is not configured")

    async def create_signed_url(self, *, object_key: str, expires_in: int) -> str:
        raise StorageError("Catalog storage is not configured")


class SupabaseCatalogStorage:
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
                    headers={**self.headers, "content-type": content_type, "x-upsert": "false"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageError("Unable to store catalog image") from exc

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
            raise StorageError("Unable to remove catalog image") from exc

    async def create_signed_url(self, *, object_key: str, expires_in: int) -> str:
        url = f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{object_key}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={"expiresIn": expires_in},
                    headers={**self.headers, "content-type": "application/json"},
                )
                response.raise_for_status()
                signed_path = str(response.json()["signedURL"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise StorageError("Unable to authorize catalog image") from exc
        if signed_path.startswith("http://") or signed_path.startswith("https://"):
            return signed_path
        return f"{self.base_url}/storage/v1{signed_path}"
