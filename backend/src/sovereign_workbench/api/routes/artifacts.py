from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from sovereign_workbench.config import get_settings
from sovereign_workbench.db.models import ArtifactRow
from sovereign_workbench.db.session import get_session
from sovereign_workbench.schemas.artifacts import Artifact

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts", response_model=list[Artifact])
async def list_artifacts(
    task_id: UUID | None = None,
    session: Session = Depends(get_session),
) -> list[Artifact]:
    stmt = select(ArtifactRow).order_by(desc(ArtifactRow.created_at))
    if task_id:
        stmt = stmt.where(ArtifactRow.task_id == str(task_id))
    rows = session.execute(stmt).scalars().all()
    return [
        Artifact(
            id=row.id,  # type: ignore[arg-type]
            task_id=row.task_id,  # type: ignore[arg-type]
            filename=row.filename,
            kind=row.kind,
            size_bytes=row.size_bytes,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/artifacts/{artifact_id}")
@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: UUID,
    session: Session = Depends(get_session),
) -> FileResponse:
    row = session.get(ArtifactRow, str(artifact_id))
    if row is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    path = Path(row.path)
    artifacts_root = get_settings().artifacts_dir.resolve()
    if artifacts_root not in path.resolve().parents:
        raise HTTPException(status_code=410, detail="artifact path is invalid")
    if not path.exists():
        raise HTTPException(status_code=410, detail="artifact file is missing")
    return FileResponse(path, filename=row.filename)
