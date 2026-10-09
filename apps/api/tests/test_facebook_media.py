import asyncio
import io

import httpx
import pytest
from PIL import Image

from agent_hub_api.facebook.media import (
    FacebookMediaDownloader,
    FacebookMediaError,
    FacebookMediaLimits,
)


def image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), color=(20, 100, 180)).save(output, format="PNG")
    return output.getvalue()


def downloader(handler: httpx.MockTransport) -> FacebookMediaDownloader:
    return FacebookMediaDownloader(
        FacebookMediaLimits(
            max_bytes=10_000,
            max_pixels=1_000,
            max_redirects=2,
            timeout_seconds=2,
            allowed_hosts=("fbcdn.net", "facebook.com"),
        ),
        transport=handler,
    )


def test_media_download_validates_each_redirect_host_and_sanitizes_image() -> None:
    content = image_bytes()

    def success(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "scontent.xx.fbcdn.net"
        return httpx.Response(
            200,
            headers={"content-type": "image/png", "content-length": str(len(content))},
            content=content,
        )

    result = asyncio.run(
        downloader(httpx.MockTransport(success)).download(
            "https://scontent.xx.fbcdn.net/private/image.png?token=secret"
        )
    )
    assert result.content_type == "image/png"
    assert (result.width, result.height) == (8, 6)

    def redirect(_: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://127.0.0.1/private"})

    with pytest.raises(FacebookMediaError, match="FACEBOOK_MEDIA_URL_REJECTED"):
        asyncio.run(
            downloader(httpx.MockTransport(redirect)).download(
                "https://scontent.xx.fbcdn.net/private/image.png"
            )
        )


def test_media_download_rejects_mime_and_byte_limits_without_logging_url() -> None:
    def wrong_mime(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"no")

    with pytest.raises(FacebookMediaError, match="FACEBOOK_MEDIA_TYPE_UNSUPPORTED"):
        asyncio.run(
            downloader(httpx.MockTransport(wrong_mime)).download(
                "https://scontent.xx.fbcdn.net/private/image"
            )
        )

    def oversized(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "image/jpeg", "content-length": "10001"},
            content=b"",
        )

    with pytest.raises(FacebookMediaError, match="FACEBOOK_MEDIA_TOO_LARGE"):
        asyncio.run(
            downloader(httpx.MockTransport(oversized)).download(
                "https://scontent.xx.fbcdn.net/private/image"
            )
        )
