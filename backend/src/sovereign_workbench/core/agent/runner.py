"""Task runner — wires the agent loop to persistence and streams events.

Kept separate from the HTTP layer so it can be driven by tests or a CLI without a
running server.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sovereign_workbench.config import Settings
from sovereign_workbench.core.agent.loop import AgentLoop, AgentRunError
from sovereign_workbench.core.agent.tools.base import ToolContext
from sovereign_workbench.core.llm.router import NoModelAvailable
from sovereign_workbench.core.sandbox import get_sandbox
from sovereign_workbench.core.security.audit import get_audit_log
from sovereign_workbench.db.models import ArtifactRow, DocumentRow, StepRow, TaskEventRow, TaskRow
from sovereign_workbench.db.session import session_scope
from sovereign_workbench.observability.logging import get_logger
from sovereign_workbench.schemas.events import AgentEvent
from sovereign_workbench.schemas.tasks import TaskOptions

log = get_logger(__name__)


class TaskRunner:
    def __init__(self, loop: AgentLoop, settings: Settings) -> None:
        self.loop = loop
        self.settings = settings
        self._workers: dict[UUID, asyncio.Task[None]] = {}
        self._signals: dict[UUID, asyncio.Event] = {}
        self._run_lock = asyncio.Lock()
        self._cancelled: set[UUID] = set()
        self._active: set[UUID] = set()

    def create_task(
        self,
        prompt: str,
        *,
        model_id: str | None,
        options: TaskOptions,
        attachments: list[str] | None = None,
    ) -> UUID:
        task_id = uuid4()
        attachment_ids = _unique_ids(attachments or [])
        self._validate_attachments(attachment_ids)
        if model_id:
            spec = self.loop.registry.get(model_id)
            if spec is None:
                raise ValueError("unknown model")
            if spec.remote and self.loop.registry.airgap:
                raise ValueError("remote models are disabled in air-gap mode")
            if not set(spec.capabilities).intersection({"chat", "plan", "code", "vision"}):
                raise ValueError("selected model cannot run agent tasks")
            if self.loop.registry.probed and not self.loop.registry.is_available(spec):
                raise ValueError("selected model is not available")
        selected_model_id = model_id
        if selected_model_id is None:
            with contextlib.suppress(NoModelAvailable):
                selected_model_id = self.loop.router.route(
                    prompt, has_image=_has_image(attachment_ids)
                ).spec.id
        with session_scope() as session:
            session.add(
                TaskRow(
                    id=str(task_id),
                    prompt=prompt,
                    status="queued",
                    model_id=selected_model_id,
                    options=options.model_dump_json(),
                    attachments=json.dumps(attachment_ids),
                )
            )
        return task_id

    async def stream(
        self,
        task_id: UUID,
        prompt: str,
        *,
        options: TaskOptions | None = None,
        attachments: list[str] | None = None,
        model_id: str | None = None,
        after: int = 0,
    ) -> AsyncIterator[AgentEvent]:
        """Subscribe to a run; disconnecting a subscriber never kills the worker."""
        if self.task_inputs(task_id) is None:
            raise ValueError("task was not found")
        signal = self._signals.get(task_id) or asyncio.Event()
        if task_id not in self._workers:
            with session_scope() as session:
                terminal = (
                    session.query(TaskEventRow)
                    .filter(TaskEventRow.task_id == str(task_id))
                    .order_by(TaskEventRow.id.desc())
                    .first()
                )
            last = AgentEvent.model_validate_json(terminal.payload) if terminal else None
            if last is None or last.type not in {"done", "error"}:
                self._signals[task_id] = signal
                worker = asyncio.create_task(self._produce(task_id))
                self._workers[task_id] = worker
                worker.add_done_callback(lambda completed: self._worker_done(task_id, completed))
        while True:
            signal.clear()
            with session_scope() as session:
                rows = (
                    session.query(TaskEventRow)
                    .filter(TaskEventRow.task_id == str(task_id), TaskEventRow.id > after)
                    .order_by(TaskEventRow.id)
                    .limit(200)
                    .all()
                )
            for row in rows:
                event = AgentEvent.model_validate_json(row.payload)
                event.id = row.id
                after = row.id
                yield event
                if event.type in {"done", "error"}:
                    return
            if rows:
                continue
            if task_id not in self._workers:
                return
            await signal.wait()

    def _worker_done(self, task_id: UUID, worker: asyncio.Task[None]) -> None:
        if worker.cancelled() and self._workers.get(task_id) is worker:
            message = "cancelled before execution started"
            self._set_status(task_id, "cancelled", error=message)
            self._store_stream_event(
                AgentEvent(
                    type="error",
                    task_id=task_id,
                    at=datetime.now(UTC),
                    data={"code": "TASK_CANCELLED", "message": message},
                )
            )
            self._workers.pop(task_id, None)
            signal = self._signals.pop(task_id, None)
            if signal:
                signal.set()
            self._cancelled.discard(task_id)

    async def _produce(self, task_id: UUID) -> None:
        try:
            # A minimum-tier machine can hold only one active inference/tool run.
            async with self._run_lock:
                inputs = self.task_inputs(task_id)
                if inputs is None:
                    return
                prompt, options, attachments, model_id = inputs
                async for event in self._execute(
                    task_id, prompt, options=options, attachments=attachments, model_id=model_id
                ):
                    self._store_stream_event(event)
        except asyncio.CancelledError:
            cancelled = task_id in self._cancelled
            message = "cancelled by user" if cancelled else "backend stopped before completion"
            self._set_status(task_id, "cancelled" if cancelled else "error", error=message)
            self._store_stream_event(
                AgentEvent(
                    type="error",
                    task_id=task_id,
                    at=datetime.now(UTC),
                    data={
                        "code": "TASK_CANCELLED" if cancelled else "TASK_INTERRUPTED",
                        "message": message,
                    },
                )
            )
        except Exception as exc:
            self._set_status(task_id, "error", error=str(exc))
            self._store_stream_event(
                AgentEvent(
                    type="error",
                    task_id=task_id,
                    at=datetime.now(UTC),
                    data={"code": "AGENT_FAILED", "message": str(exc)},
                )
            )
        finally:
            self._workers.pop(task_id, None)
            signal = self._signals.pop(task_id, None)
            if signal:
                signal.set()
            self._cancelled.discard(task_id)

    def _store_stream_event(self, event: AgentEvent) -> None:
        with session_scope() as session:
            session.add(TaskEventRow(task_id=str(event.task_id), payload=event.model_dump_json()))
        signal = self._signals.get(event.task_id)
        if signal:
            signal.set()

    async def shutdown(self) -> None:
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    def recover_interrupted(self) -> None:
        with session_scope() as session:
            rows = session.query(TaskRow).filter(TaskRow.status == "running").all()
            for row in rows:
                row.status = "error"
                row.error = "backend stopped before completion; submit the task again"
                session.add(
                    TaskEventRow(
                        task_id=row.id,
                        payload=AgentEvent(
                            type="error",
                            task_id=UUID(row.id),
                            at=datetime.now(UTC),
                            data={"code": "TASK_INTERRUPTED", "message": row.error},
                        ).model_dump_json(),
                    )
                )

    async def _execute(
        self,
        task_id: UUID,
        prompt: str,
        *,
        options: TaskOptions | None = None,
        attachments: list[str] | None = None,
        model_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        options = options or TaskOptions()
        workspace = self.settings.workspace_dir / str(task_id)
        workspace.mkdir(parents=True, exist_ok=True)

        with session_scope() as session:
            existing = session.get(TaskRow, str(task_id))
        if existing is None:
            raise ValueError("task was not found")
        if existing.status == "done":
            for event in self._persisted_events(task_id):
                yield event
            artifacts = _task_artifacts(task_id)
            for artifact in artifacts:
                yield AgentEvent(
                    type="artifact",
                    task_id=task_id,
                    at=datetime.now(UTC),
                    data=artifact,
                )
            yield AgentEvent(
                type="done",
                task_id=task_id,
                at=datetime.now(UTC),
                data={"artifacts": [artifact["filename"] for artifact in artifacts]},
            )
            return
        if existing.status in {"error", "cancelled"}:
            yield AgentEvent(
                type="error",
                task_id=task_id,
                at=datetime.now(UTC),
                data={
                    "code": "TASK_CANCELLED" if existing.status == "cancelled" else "TASK_FAILED",
                    "message": existing.error or "task failed",
                },
            )
            return
        if task_id in self._active or existing.status == "running":
            yield AgentEvent(
                type="error",
                task_id=task_id,
                at=datetime.now(UTC),
                data={"code": "TASK_RUNNING", "message": "task already has an active stream"},
            )
            return

        ctx = ToolContext(
            workspace_dir=workspace,
            artifacts_dir=self.settings.artifacts_dir,
            settings=self.settings,
            task_id=task_id,
            allow_network=options.allow_network and not self.settings.airgap,
            write_files=options.write_files,
            run_code=options.run_code,
            sandbox=get_sandbox() if options.run_code else None,
            extras={
                "prompt": prompt,
                "attachments": attachments or [],
                "max_steps": options.max_steps,
                "is_cancelled": lambda: task_id in self._cancelled,
            },
        )

        self._set_status(task_id, "running")
        self._active.add(task_id)
        get_audit_log().record(
            "task_started", actor="agent", detail=prompt[:200], data={"task_id": str(task_id)}
        )
        step_index = 0
        try:
            self._materialize_attachments(workspace, attachments or [])
            async for event in self.loop.run(
                task_id,
                prompt,
                ctx,
                register_artifact=lambda path, kind: self._register_artifact(task_id, path, kind),
                model_id=model_id,
            ):
                if event.type == "done" and task_id in self._cancelled:
                    raise AgentRunError("task cancelled by user", code="TASK_CANCELLED")
                if event.type in {"step_start", "tool_call", "tool_result", "plan"}:
                    step_index = self._persist_event(task_id, step_index, event)
                if event.type == "done":
                    self._set_status(task_id, "done")
                    get_audit_log().record(
                        "task_finished",
                        actor="agent",
                        detail="done",
                        data={"task_id": str(task_id)},
                    )
                yield event
        except Exception as exc:
            log.exception("task failed")
            cancelled = getattr(exc, "code", None) == "TASK_CANCELLED"
            self._set_status(task_id, "cancelled" if cancelled else "error", error=str(exc))
            get_audit_log().record(
                "task_cancelled" if cancelled else "task_failed",
                actor="agent",
                detail=str(exc),
                data={"task_id": str(task_id)},
            )
            error_data: dict[str, Any] = {"message": str(exc), "code": "AGENT_FAILED"}
            if hasattr(exc, "code"):
                error_data["code"] = exc.code
            if hasattr(exc, "tool") and exc.tool:
                error_data["tool"] = exc.tool
            error_event = AgentEvent(
                type="error",
                task_id=task_id,
                at=datetime.now(UTC),
                data=error_data,
            )
            yield error_event
        finally:
            self._active.discard(task_id)

    # -- helpers ------------------------------------------------------------
    def _materialize_attachments(self, workspace: Path, document_ids: list[str]) -> None:
        if not document_ids:
            return
        with session_scope() as session:
            rows = session.query(DocumentRow).filter(DocumentRow.id.in_(document_ids)).all()
            if len(rows) != len(document_ids):
                raise AgentRunError(
                    "an attached document was deleted before this task started",
                    code="ATTACHMENT_MISSING",
                )
            for row in rows:
                source = Path(row.path)
                if not source.is_file():
                    raise AgentRunError(
                        f"attached document is missing: {row.filename}", code="ATTACHMENT_MISSING"
                    )
                shutil.copy2(source, workspace / Path(row.filename).name)

    def _validate_attachments(self, document_ids: list[str]) -> None:
        if not document_ids:
            return
        with session_scope() as session:
            rows = session.query(DocumentRow).filter(DocumentRow.id.in_(document_ids)).all()
        found = {row.id: row for row in rows}
        missing = [document_id for document_id in document_ids if document_id not in found]
        if missing:
            raise ValueError(f"attachment document not found: {missing[0]}")
        unavailable = [
            document_id
            for document_id in document_ids
            if found[document_id].status == "failed" or not Path(found[document_id].path).is_file()
        ]
        if unavailable:
            raise ValueError(f"attachment document is unavailable: {unavailable[0]}")
        filenames = [Path(row.filename).name.casefold() for row in rows]
        if len(filenames) != len(set(filenames)):
            raise ValueError("attachments contain duplicate filenames")

    def _register_artifact(self, task_id: UUID, path: Path, kind: str) -> dict[str, object]:
        workspace = (self.settings.workspace_dir / str(task_id)).resolve()
        if workspace not in path.resolve().parents or not path.is_file():
            raise AgentRunError("artifact source is outside the task workspace")
        artifact_id = uuid4()
        target_dir = self.settings.artifacts_dir / str(task_id) / str(artifact_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / path.name
        if path.resolve() != target.resolve():
            shutil.copy2(path, target)
        with session_scope() as session:
            session.add(
                ArtifactRow(
                    id=str(artifact_id),
                    task_id=str(task_id),
                    filename=target.name,
                    kind=kind,
                    path=str(target),
                    size_bytes=target.stat().st_size if target.exists() else 0,
                )
            )
        get_audit_log().record(
            "artifact_created", actor="agent", detail=target.name, data={"task_id": str(task_id)}
        )
        return {
            "id": str(artifact_id),
            "task_id": str(task_id),
            "filename": target.name,
            "kind": kind,
            "size_bytes": target.stat().st_size if target.exists() else 0,
            "created_at": datetime.now(UTC).isoformat(),
        }

    def _persist_event(self, task_id: UUID, step_index: int, event: AgentEvent) -> int:
        kind = event.type
        title = str(event.data.get("title") or event.data.get("tool") or event.type)
        with session_scope() as session:
            session.add(
                StepRow(
                    task_id=str(task_id),
                    index=step_index,
                    kind=kind,
                    title=title[:250],
                    detail=json.dumps(event.data)[:8000],
                    tool=event.data.get("tool"),
                    args=json.dumps(event.data.get("args")) if event.data.get("args") else None,
                    result=(
                        json.dumps(event.data)
                        if event.type == "tool_result"
                        else (
                            json.dumps(event.data.get("output"))
                            if event.data.get("output")
                            else None
                        )
                    ),
                    ok=event.data.get("ok"),
                    started_at=event.at,
                    ended_at=event.at,
                )
            )
        return step_index + 1

    def _persisted_events(self, task_id: UUID) -> list[AgentEvent]:
        """Rebuild the useful part of an event stream after a process restart."""
        allowed = {"plan", "step_start", "tool_call", "tool_result"}
        with session_scope() as session:
            rows = (
                session.query(StepRow)
                .filter(StepRow.task_id == str(task_id))
                .order_by(StepRow.index)
                .all()
            )
        events: list[AgentEvent] = []
        for row in rows:
            if row.kind not in allowed:
                continue
            try:
                data = json.loads(row.detail or "{}")
            except json.JSONDecodeError:
                data = {"title": row.title}
            if not isinstance(data, dict):
                data = {"value": data}
            events.append(
                AgentEvent(
                    type=row.kind,  # type: ignore[arg-type]
                    task_id=task_id,
                    at=row.ended_at or row.started_at or datetime.now(UTC),
                    data=data,
                )
            )
        return events

    def task_inputs(self, task_id: UUID) -> tuple[str, TaskOptions, list[str], str | None] | None:
        with session_scope() as session:
            row = session.get(TaskRow, str(task_id))
            if row is None:
                return None
            try:
                raw_options = json.loads(row.options or "{}")
                raw_attachments = json.loads(row.attachments or "[]")
            except json.JSONDecodeError:
                raw_options = {}
                raw_attachments = []
            return (
                row.prompt,
                TaskOptions.model_validate(raw_options),
                [str(item) for item in raw_attachments],
                row.model_id,
            )

    def _set_status(self, task_id: UUID, status: str, *, error: str | None = None) -> None:
        with session_scope() as session:
            row = session.get(TaskRow, str(task_id))
            if row is not None:
                row.status = status
                row.error = error
                row.updated_at = datetime.now(UTC)

    def cancel_task(self, task_id: UUID) -> bool:
        with session_scope() as session:
            row = session.get(TaskRow, str(task_id))
            if row is None or row.status in {"done", "error", "cancelled"}:
                return False
            worker = self._workers.get(task_id)
            if worker is not None:
                self._cancelled.add(task_id)
                worker.cancel()
            row.status = "cancelled"
            row.error = "cancelled by user"
            row.updated_at = datetime.now(UTC)
        get_audit_log().record(
            "task_cancelled",
            actor="user",
            detail="cancelled by user",
            data={"task_id": str(task_id)},
        )
        return True


def _unique_ids(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _has_image(document_ids: list[str]) -> bool:
    if not document_ids:
        return False
    with session_scope() as session:
        rows = session.query(DocumentRow.filename).filter(DocumentRow.id.in_(document_ids)).all()
    image_suffixes = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
    return any(Path(row[0]).suffix.lower() in image_suffixes for row in rows)


def _task_artifacts(task_id: UUID) -> list[dict[str, object]]:
    with session_scope() as session:
        rows = session.query(ArtifactRow).filter(ArtifactRow.task_id == str(task_id)).all()
    return [
        {
            "id": row.id,
            "task_id": row.task_id,
            "filename": row.filename,
            "kind": row.kind,
            "size_bytes": row.size_bytes,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
