from __future__ import annotations

import hashlib
from dataclasses import dataclass

from agent_hub_api.knowledge.extraction import normalize_document_text


@dataclass(frozen=True, slots=True)
class TextChunk:
    position: int
    content: str
    content_sha256: str
    source_locator: str


def chunk_text(
    value: str,
    *,
    chunk_size: int,
    overlap: int,
    max_chunks: int,
    source_prefix: str,
) -> list[TextChunk]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size or max_chunks < 1:
        raise ValueError("Invalid chunking limits")
    text = normalize_document_text(value)
    if not text:
        return []
    chunks: list[TextChunk] = []
    start = 0
    while start < len(text):
        hard_end = min(start + chunk_size, len(text))
        end = hard_end
        if hard_end < len(text):
            paragraph_break = text.rfind("\n\n", start + chunk_size // 2, hard_end)
            word_break = text.rfind(" ", start + chunk_size // 2, hard_end)
            end = max(paragraph_break + 2 if paragraph_break >= 0 else 0, word_break + 1)
            if end <= start:
                end = hard_end
        content = text[start:end].strip()
        if content:
            position = len(chunks)
            chunks.append(
                TextChunk(
                    position=position,
                    content=content,
                    content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    source_locator=f"{source_prefix}#chunk-{position + 1}",
                )
            )
            if len(chunks) > max_chunks:
                raise ValueError("DOCUMENT_CHUNK_LIMIT_EXCEEDED")
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks
