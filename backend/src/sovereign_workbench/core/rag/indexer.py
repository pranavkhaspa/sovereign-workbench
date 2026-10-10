"""Document ingestion: extract -> chunk -> embed -> persist."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sovereign_workbench.config import get_settings
from sovereign_workbench.core.rag.chunker import chunk_pages
from sovereign_workbench.core.rag.embeddings import get_embedder
from sovereign_workbench.core.rag.extract import extract_pages
from sovereign_workbench.db.models import ChunkRow, DocumentRow
from sovereign_workbench.db.session import session_scope
from sovereign_workbench.observability.logging import get_logger
from sovereign_workbench.schemas.documents import Document

log = get_logger(__name__)


def index_document(
    path: Path,
    *,
    filename: str,
    content_type: str = "application/octet-stream",
) -> Document:
    settings = get_settings()
    pages = extract_pages(path)
    chunks = chunk_pages(pages, size=settings.chunk_size, overlap=settings.chunk_overlap)
    embeddings = get_embedder().embed([c.text for c in chunks]) if chunks else []

    with session_scope() as session:
        document = DocumentRow(
            filename=filename,
            content_type=content_type,
            size_bytes=path.stat().st_size if path.exists() else 0,
            path=str(path),
            chunk_count=len(chunks),
            status="indexed" if chunks else "empty",
        )
        session.add(document)
        session.flush()
        for index, chunk in enumerate(chunks):
            session.add(
                ChunkRow(
                    document_id=document.id,
                    index=index,
                    text=chunk.text,
                    page=chunk.page,
                    span=chunk.span,
                    embedding=json.dumps(embeddings[index]) if embeddings else None,
                )
            )
        session.flush()
        document_id = document.id

    log.info(
        "indexed document",
        extra={"extra_fields": {"filename": filename, "chunks": len(chunks)}},
    )
    return Document(
        id=document_id,  # type: ignore[arg-type]
        filename=filename,
        content_type=content_type,
        size_bytes=path.stat().st_size if path.exists() else 0,
        chunk_count=len(chunks),
        status="indexed" if chunks else "empty",
        created_at=datetime.now(UTC),
    )
