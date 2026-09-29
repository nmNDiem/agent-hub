from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path


class ExtractionError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ExtractionLimits:
    max_pages: int
    max_chars: int
    wall_seconds: int
    cpu_seconds: int
    memory_bytes: int
    output_bytes: int


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    text: str
    page_count: int | None


def normalize_document_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        character
        for character in normalized
        if character in {"\n", "\t"} or ord(character) >= 32
    ).strip()


def extract_text_file(path: Path, *, max_chars: int) -> ExtractedDocument:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise ExtractionError("TEXT_ENCODING_INVALID") from exc
    normalized = normalize_document_text(text)
    if not normalized:
        raise ExtractionError("TEXT_CONTENT_EMPTY")
    if len(normalized) > max_chars:
        raise ExtractionError("DOCUMENT_TEXT_LIMIT_EXCEEDED")
    return ExtractedDocument(text=normalized, page_count=None)


def _extract_pdf_sync(
    path: Path, limits: ExtractionLimits, child_script: Path | None = None
) -> ExtractedDocument:
    with tempfile.TemporaryDirectory(prefix="agenthub-pdf-output-") as temporary:
        output_path = Path(temporary) / "result.json"
        command = [
            sys.executable,
            "-I",
            str(child_script or Path(__file__).with_name("pdf_child.py")),
            str(path),
            str(output_path),
            str(limits.max_pages),
            str(limits.max_chars),
            str(limits.cpu_seconds),
            str(limits.memory_bytes),
            str(limits.output_bytes),
        ]
        process = subprocess.Popen(  # noqa: S603
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        try:
            process.wait(timeout=limits.wall_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise ExtractionError("PDF_PARSE_TIMEOUT") from exc
        if process.returncode != 0 or not output_path.is_file():
            raise ExtractionError("PDF_RESOURCE_LIMIT")
        try:
            if output_path.stat().st_size > limits.output_bytes:
                raise ExtractionError("PDF_OUTPUT_LIMIT_EXCEEDED")
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExtractionError("PDF_INVALID") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
            raise ExtractionError("PDF_INVALID")
        if not payload["ok"]:
            code = payload.get("error_code")
            raise ExtractionError(code if isinstance(code, str) else "PDF_INVALID")
        text = payload.get("text")
        page_count = payload.get("page_count")
        if not isinstance(text, str) or not isinstance(page_count, int):
            raise ExtractionError("PDF_INVALID")
        return ExtractedDocument(text=text, page_count=page_count)


async def extract_pdf(
    path: Path, limits: ExtractionLimits, *, child_script: Path | None = None
) -> ExtractedDocument:
    return await asyncio.to_thread(_extract_pdf_sync, path, limits, child_script)
