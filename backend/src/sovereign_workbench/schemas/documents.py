from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Citation(BaseModel):
    document_id: UUID
    filename: str
    page: int | None = None
    span: str | None = None
    score: float = 0.0


class Chunk(BaseModel):
    id: str
    text: str
    citation: Citation


class Document(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    chunk_count: int
    status: str
    created_at: datetime


class DocumentUploadResult(BaseModel):
    document_id: UUID
    chunks: int
    status: str


class DocumentSearchRequest(BaseModel):
    query: str
    top_k: int = 5
