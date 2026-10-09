from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from agent_hub_api.core.errors import ApiError
from agent_hub_api.widget.image_validation import ValidatedImage, validate_and_sanitize_image


class FacebookMediaError(RuntimeError):
    def __init__(self, safe_code: str, *, retryable: bool = False) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class FacebookMediaLimits:
    max_bytes: int
    max_pixels: int
    max_redirects: int
    timeout_seconds: int
    allowed_hosts: tuple[str, ...]


class FacebookMediaDownloader:
    def __init__(
        self,
        limits: FacebookMediaLimits,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.limits = limits
        self.transport = transport

    async def download(self, source_url: str) -> ValidatedImage:
        current = source_url
        try:
            async with httpx.AsyncClient(
                timeout=self.limits.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                for redirect_count in range(self.limits.max_redirects + 1):
                    self._validate_url(current)
                    async with client.stream("GET", current) as response:
                        if response.is_redirect:
                            if redirect_count >= self.limits.max_redirects:
                                raise FacebookMediaError("FACEBOOK_MEDIA_REDIRECT_LIMIT")
                            location = response.headers.get("location")
                            if not location:
                                raise FacebookMediaError("FACEBOOK_MEDIA_INVALID_REDIRECT")
                            current = urljoin(current, location)
                            continue
                        if response.status_code >= 500 or response.status_code == 429:
                            raise FacebookMediaError("FACEBOOK_MEDIA_UNAVAILABLE", retryable=True)
                        if response.is_error:
                            raise FacebookMediaError("FACEBOOK_MEDIA_REJECTED")
                        declared = response.headers.get("content-type", "").split(";", 1)[0]
                        if declared not in {"image/jpeg", "image/png", "image/webp"}:
                            raise FacebookMediaError("FACEBOOK_MEDIA_TYPE_UNSUPPORTED")
                        content_length = response.headers.get("content-length")
                        if content_length is not None:
                            try:
                                if int(content_length) > self.limits.max_bytes:
                                    raise FacebookMediaError("FACEBOOK_MEDIA_TOO_LARGE")
                            except ValueError as exc:
                                raise FacebookMediaError("FACEBOOK_MEDIA_INVALID_LENGTH") from exc
                        chunks: list[bytes] = []
                        size = 0
                        async for chunk in response.aiter_bytes(64 * 1024):
                            size += len(chunk)
                            if size > self.limits.max_bytes:
                                raise FacebookMediaError("FACEBOOK_MEDIA_TOO_LARGE")
                            chunks.append(chunk)
                        try:
                            return validate_and_sanitize_image(
                                b"".join(chunks),
                                declared_content_type=declared,
                                max_bytes=self.limits.max_bytes,
                                max_pixels=self.limits.max_pixels,
                            )
                        except ApiError as exc:
                            raise FacebookMediaError(exc.code) from exc
        except FacebookMediaError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise FacebookMediaError("FACEBOOK_MEDIA_UNAVAILABLE", retryable=True) from exc
        raise FacebookMediaError("FACEBOOK_MEDIA_INVALID_REDIRECT")

    def _validate_url(self, value: str) -> None:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise FacebookMediaError("FACEBOOK_MEDIA_URL_REJECTED") from exc
        host = (parsed.hostname or "").casefold().rstrip(".")
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or parsed.fragment
            or not any(
                host == allowed or host.endswith(f".{allowed}")
                for allowed in self.limits.allowed_hosts
            )
        ):
            raise FacebookMediaError("FACEBOOK_MEDIA_URL_REJECTED")
