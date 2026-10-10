from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Artifact(BaseModel):
    id: UUID
    task_id: UUID | None = None
    filename: str
    kind: str  # docx | pptx | xlsx | code | log | text
    size_bytes: int
    created_at: datetime
