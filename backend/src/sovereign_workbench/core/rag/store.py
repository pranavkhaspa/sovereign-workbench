"""Cosine vector search over chunks stored in SQLite.

The corpus is small (an organisation's manuals), so brute-force cosine in Python is
faster to reason about than a separate vector server and keeps the 8 GB machine happy.
"""

from __future__ import annotations

import json
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from sovereign_workbench.db.models import ChunkRow, DocumentRow
from sovereign_workbench.schemas.documents import Chunk, Citation


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def search(session: Session, query_vector: list[float], top_k: int = 5) -> list[Chunk]:
    rows = session.execute(
        select(ChunkRow, DocumentRow).join(DocumentRow, ChunkRow.document_id == DocumentRow.id)
    ).all()
    scored: list[tuple[float, ChunkRow, DocumentRow]] = []
    for chunk, document in rows:
        if not chunk.embedding:
            continue
        try:
            vector = json.loads(chunk.embedding)
        except json.JSONDecodeError:
            continue
        score = cosine(query_vector, vector)
        if score > 0:
            scored.append((score, chunk, document))
    scored.sort(key=lambda item: item[0], reverse=True)
    results: list[Chunk] = []
    for score, chunk, document in scored[:top_k]:
        results.append(
            Chunk(
                id=chunk.id,
                text=chunk.text,
                citation=Citation(
                    document_id=document.id,  # type: ignore[arg-type]
                    filename=document.filename,
                    page=chunk.page,
                    span=chunk.span,
                    score=round(score, 4),
                ),
            )
        )
    return results
