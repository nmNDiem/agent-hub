from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

from fastapi import status
from PIL import Image, ImageOps, UnidentifiedImageError

from agent_hub_api.core.errors import ApiError


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    content: bytes
    content_type: str
    extension: str
    width: int
    height: int


def validate_and_sanitize_image(
    content: bytes,
    *,
    declared_content_type: str,
    max_bytes: int,
    max_pixels: int,
) -> ValidatedImage:
    if not content or len(content) > max_bytes:
        raise ApiError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "IMAGE_TOO_LARGE",
            "Ảnh vượt quá giới hạn dung lượng.",
        )
    allowed = {
        "JPEG": ("image/jpeg", "jpg"),
        "PNG": ("image/png", "png"),
        "WEBP": ("image/webp", "webp"),
    }
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                source.verify()
            with Image.open(io.BytesIO(content)) as source:
                image_format = source.format or ""
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise ApiError(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        "IMAGE_PIXELS_EXCEEDED",
                        "Kích thước pixel của ảnh quá lớn.",
                    )
                if getattr(source, "n_frames", 1) != 1:
                    raise ValueError("Animated images are not supported")
                source.load()
                sanitized = ImageOps.exif_transpose(source)
                normalized = sanitized.copy()
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "INVALID_IMAGE",
            "Tệp tải lên không phải ảnh hợp lệ.",
        ) from exc
    detected = allowed.get(image_format)
    if detected is None or declared_content_type.lower() != detected[0]:
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "IMAGE_TYPE_MISMATCH",
            "Định dạng ảnh không khớp với nội dung tệp.",
        )
    output = io.BytesIO()
    if image_format == "JPEG":
        normalized.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
    elif image_format == "PNG":
        if normalized.mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
            normalized = normalized.convert("RGBA")
        normalized.save(output, format="PNG", optimize=True)
    else:
        if normalized.mode not in {"RGB", "RGBA"}:
            normalized = normalized.convert("RGBA")
        normalized.save(output, format="WEBP", quality=90, method=4)
    sanitized_content = output.getvalue()
    if not sanitized_content or len(sanitized_content) > max_bytes:
        raise ApiError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "IMAGE_TOO_LARGE",
            "Ảnh sau khi xử lý vượt quá giới hạn dung lượng.",
        )
    return ValidatedImage(
        content=sanitized_content,
        content_type=detected[0],
        extension=detected[1],
        width=width,
        height=height,
    )
