from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile, status

from agent_hub_api.core.errors import ApiError

PDF_MIME = "application/pdf"
TEXT_MIME = "text/plain"


@dataclass(frozen=True, slots=True)
class StagedKnowledgeUpload:
    path: Path
    filename: str
    mime_type: str
    byte_size: int
    sha256: str

    def cleanup(self) -> None:
        self.path.unlink(missing_ok=True)


def _safe_filename(filename: str | None) -> str:
    cleaned = Path((filename or "document").replace("\x00", "")).name.strip()
    if not cleaned or len(cleaned) > 255:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_FILENAME",
            "Tên tệp không hợp lệ.",
        )
    return cleaned


def _validate_type(filename: str, declared_type: str, first_bytes: bytes) -> str:
    suffix = Path(filename).suffix.casefold()
    if declared_type == PDF_MIME and suffix == ".pdf" and first_bytes.startswith(b"%PDF-"):
        return PDF_MIME
    if declared_type == TEXT_MIME and suffix == ".txt" and not first_bytes.startswith(b"%PDF-"):
        return TEXT_MIME
    raise ApiError(
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        "KNOWLEDGE_FILE_TYPE_INVALID",
        "Chỉ chấp nhận tệp PDF hoặc TXT hợp lệ.",
    )


async def stage_knowledge_upload(
    upload: UploadFile, *, max_bytes: int
) -> StagedKnowledgeUpload:
    filename = _safe_filename(upload.filename)
    declared_type = (upload.content_type or "").split(";", 1)[0].strip().casefold()
    descriptor, raw_path = tempfile.mkstemp(prefix="agenthub-knowledge-", suffix=".upload")
    path = Path(raw_path)
    digest = hashlib.sha256()
    total = 0
    first_bytes = b""
    try:
        with os.fdopen(descriptor, "wb") as output:
            while chunk := await upload.read(64 * 1024):
                if not first_bytes:
                    first_bytes = chunk[:16]
                total += len(chunk)
                if total > max_bytes:
                    raise ApiError(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        "KNOWLEDGE_FILE_TOO_LARGE",
                        "Tệp kiến thức vượt quá giới hạn cho phép.",
                    )
                digest.update(chunk)
                await asyncio.to_thread(output.write, chunk)
        if total == 0:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "KNOWLEDGE_FILE_EMPTY",
                "Tệp kiến thức không được để trống.",
            )
        mime_type = _validate_type(filename, declared_type, first_bytes)
        return StagedKnowledgeUpload(
            path=path,
            filename=filename,
            mime_type=mime_type,
            byte_size=total,
            sha256=digest.hexdigest(),
        )
    except BaseException:
        path.unlink(missing_ok=True)
        raise
