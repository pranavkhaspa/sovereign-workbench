from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from sovereign_workbench.api.deps import get_task_runner
from sovereign_workbench.core.agent.runner import TaskRunner
from sovereign_workbench.schemas.tasks import TaskCreate

router = APIRouter(tags=["chat"])


def _sse(event_type: str, payload: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


@router.post("/chat")
async def chat(
    payload: TaskCreate,
    runner: TaskRunner = Depends(get_task_runner),
) -> StreamingResponse:
    try:
        task_id = runner.create_task(
            payload.prompt,
            model_id=payload.model_id,
            options=payload.options,
            attachments=payload.attachments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def event_stream():
        yield _sse("task_created", {"task_id": str(task_id), "status": "queued"})
        async for event in runner.stream(
            task_id,
            payload.prompt,
            options=payload.options,
            attachments=payload.attachments,
            model_id=payload.model_id,
        ):
            yield _sse(event.type, event.model_dump(mode="json"))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
