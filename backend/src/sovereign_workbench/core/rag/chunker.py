"""Simple, dependency-free text chunker with page awareness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RawChunk:
    text: str
    page: int | None
    span: str | None = None


def chunk_pages(
    pages: list[tuple[int | None, str]],
    *,
    size: int = 900,
    overlap: int = 150,
) -> list[RawChunk]:
    if size <= overlap:
        raise ValueError("size must be greater than overlap")
    chunks: list[RawChunk] = []
    for page, text in pages:
        normalized = " ".join(text.split())
        if not normalized:
            continue
        start = 0
        while start < len(normalized):
            end = min(start + size, len(normalized))
            if end < len(normalized):
                cut = normalized.rfind(" ", start + size // 2, end)
                if cut > start:
                    end = cut
            chunks.append(
                RawChunk(
                    text=normalized[start:end].strip(),
                    page=page,
                    span=f"{start}:{end}",
                )
            )
            if end >= len(normalized):
                break
            start = max(end - overlap, start + 1)
    return [c for c in chunks if c.text]
