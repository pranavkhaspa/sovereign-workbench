from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from sovereign_workbench.api.deps import get_task_runner
from sovereign_workbench.core.agent.runner import TaskRunner
from sovereign_workbench.core.llm.registry import get_registry
from sovereign_workbench.db.models import ArtifactRow, StepRow, TaskRow
from sovereign_workbench.db.session import get_session
from sovereign_workbench.schemas.artifacts import Artifact
from sovereign_workbench.schemas.tasks import Task, TaskCreate, TaskStep

router = APIRouter(tags=["tasks"])


def _to_task(session: Session, row: TaskRow) -> Task:
    steps = (
        session.execute(select(StepRow).where(StepRow.task_id == row.id).order_by(StepRow.index))
        .scalars()
        .all()
    )
    artifacts = (
        session.execute(select(ArtifactRow).where(ArtifactRow.task_id == row.id)).scalars().all()
    )
    return Task(
        id=row.id,  # type: ignore[arg-type]
        prompt=row.prompt,
        status=row.status,
        model_id=row.model_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        attachments=_attachments(row),
        error=row.error,
        steps=[
            TaskStep(
                index=s.index,
                kind=s.kind,
                title=s.title,
                detail=s.detail,
                tool=s.tool,
                ok=s.ok,
                args=_json_dict(s.args),
                result=_json_dict(s.result),
                started_at=s.started_at,
                ended_at=s.ended_at,
            )
            for s in steps
        ],
        artifacts=[
            Artifact(
                id=a.id,  # type: ignore[arg-type]
                task_id=a.task_id,  # type: ignore[arg-type]
                filename=a.filename,
                kind=a.kind,
                size_bytes=a.size_bytes,
                created_at=a.created_at,
            )
            for a in artifacts
        ],
    )


@router.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    payload: TaskCreate,
    runner: TaskRunner = Depends(get_task_runner),
    session: Session = Depends(get_session),
) -> Task:
    if payload.model_id:
        spec = get_registry().get(payload.model_id)
        if spec is None:
            raise HTTPException(status_code=422, detail="unknown or unavailable model")
        if spec.remote and get_registry().airgap:
            raise HTTPException(
                status_code=403,
                detail="remote models are disabled in air-gap mode",
            )
    try:
        task_id = runner.create_task(
            payload.prompt,
            model_id=payload.model_id,
            options=payload.options,
            attachments=payload.attachments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = session.get(TaskRow, str(task_id))
    if row is None:
        raise HTTPException(status_code=500, detail="task was not persisted")
    return _to_task(session, row)


@router.get("/tasks/{task_id}/events")
async def task_events(
    task_id: UUID,
    after: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None),
    runner: TaskRunner = Depends(get_task_runner),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    if last_event_id is not None:
        try:
            after = max(after, int(last_event_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid Last-Event-ID") from exc
    inputs = runner.task_inputs(task_id)
    if inputs is None:
        raise HTTPException(status_code=404, detail="task not found")
    prompt, options, attachments, model_id = inputs
    row = session.get(TaskRow, str(task_id))
    status = row.status if row is not None else "queued"

    async def event_stream():
        yield _sse("task_created", {"task_id": str(task_id), "status": status})
        try:
            async for event in runner.stream(
                task_id,
                prompt,
                options=options,
                attachments=attachments,
                model_id=model_id,
                after=after,
            ):
                yield _sse(event.type, event.model_dump(mode="json"), event.id)
        except Exception as exc:
            yield _sse(
                "error",
                {
                    "type": "error",
                    "task_id": str(task_id),
                    "data": {"code": "STREAM_FAILED", "message": str(exc)},
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks", response_model=list[Task])
async def list_tasks(
    limit: int = 50,
    cursor: UUID | None = None,
    session: Session = Depends(get_session),
) -> list[Task]:
    statement = select(TaskRow).order_by(desc(TaskRow.created_at), desc(TaskRow.id))
    if cursor is not None:
        previous = session.get(TaskRow, str(cursor))
        if previous is None:
            raise HTTPException(status_code=422, detail="unknown task cursor")
        statement = statement.where(
            (TaskRow.created_at < previous.created_at)
            | ((TaskRow.created_at == previous.created_at) & (TaskRow.id < previous.id))
        )
    rows = session.execute(statement.limit(min(max(limit, 1), 200))).scalars().all()
    return [_to_task(session, row) for row in rows]


@router.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: UUID, session: Session = Depends(get_session)) -> Task:
    row = session.get(TaskRow, str(task_id))
    if row is None:
        raise HTTPException(status_code=404, detail="task not found")
    return _to_task(session, row)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: UUID, runner: TaskRunner = Depends(get_task_runner)
) -> dict[str, bool]:
    if runner.task_inputs(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    if not runner.cancel_task(task_id):
        raise HTTPException(status_code=409, detail="task cannot be cancelled")
    return {"ok": True}


def _attachments(row: TaskRow) -> list[str]:
    try:
        value = json.loads(row.attachments or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value if item]


def _sse(event_type: str, payload: dict[str, object], event_id: int | None = None) -> str:
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return f"{prefix}event: {event_type}\ndata: {json.dumps(payload)}\n\n"


def _json_dict(raw: str | None) -> dict[str, object] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(value, dict):
        return value
    return {"output": value}
