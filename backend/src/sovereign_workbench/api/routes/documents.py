from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from sovereign_workbench.config import get_settings
from sovereign_workbench.core.rag.indexer import index_document
from sovereign_workbench.core.rag.retriever import get_retriever
from sovereign_workbench.db.models import DocumentRow
from sovereign_workbench.db.session import get_session
from sovereign_workbench.schemas.documents import (
    Chunk,
    Document,
    DocumentSearchRequest,
    DocumentUploadResult,
)

router = APIRouter(tags=["documents"])
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.post("/documents", response_model=DocumentUploadResult, status_code=201)
def upload_document(file: UploadFile = File(...)) -> DocumentUploadResult:
    settings = get_settings()
    settings.ensure_dirs()
    filename = Path(file.filename or "upload.bin").name
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=422, detail="invalid filename")
    if len(filename) > 180:
        raise HTTPException(status_code=422, detail="filename is too long")
    allowed_suffixes = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
        ".webp",
        ".docx",
        ".txt",
        ".md",
        ".markdown",
        ".csv",
        ".xlsx",
        ".xlsm",
    }
    if Path(filename).suffix.lower() not in allowed_suffixes:
        raise HTTPException(status_code=415, detail="unsupported document type")
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).stem).strip("._") or "upload"
    safe_filename = f"{safe_stem}{Path(filename).suffix.lower()}"
    destination = settings.uploads_dir / f"{uuid4().hex}-{safe_filename}"
    size = 0
    try:
        with destination.open("wb") as handle:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > _MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="document exceeds 50 MB limit")
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    try:
        document = index_document(
            destination,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422, detail=f"document could not be indexed: {exc}"
        ) from exc
    return DocumentUploadResult(
        document_id=document.id, chunks=document.chunk_count, status=document.status
    )


@router.get("/documents", response_model=list[Document])
async def list_documents(session: Session = Depends(get_session)) -> list[Document]:
    rows = (
        session.execute(select(DocumentRow).order_by(desc(DocumentRow.created_at))).scalars().all()
    )
    return [
        Document(
            id=row.id,  # type: ignore[arg-type]
            filename=row.filename,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            chunk_count=row.chunk_count,
            status=row.status,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/documents/search", response_model=list[Chunk])
def search_documents(payload: DocumentSearchRequest) -> list[Chunk]:
    if not payload.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    return get_retriever().search(payload.query, top_k=min(max(payload.top_k, 1), 20))


@router.get("/documents/search", response_model=list[Chunk], include_in_schema=False)
async def search_documents_legacy(q: str, top_k: int = 5) -> list[Chunk]:
    if not q.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    return get_retriever().search(q, top_k=min(max(top_k, 1), 20))


@router.get("/documents/{document_id}", response_model=Document)
async def get_document(document_id: UUID, session: Session = Depends(get_session)) -> Document:
    row = session.get(DocumentRow, str(document_id))
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    return Document(
        id=row.id,  # type: ignore[arg-type]
        filename=row.filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        chunk_count=row.chunk_count,
        status=row.status,
        created_at=row.created_at,
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID, session: Session = Depends(get_session)
) -> dict[str, bool]:
    row = session.get(DocumentRow, str(document_id))
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    path = Path(row.path)
    session.delete(row)
    session.commit()
    path.unlink(missing_ok=True)
    return {"ok": True}
