"""The agent loop: plan -> act -> observe -> reflect -> answer.

Yields :class:`AgentEvent` objects so the API can stream the trajectory over SSE.
The loop is bounded (:attr:`Settings.max_agent_steps`) so a weak machine or a confused
model can never run away.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sovereign_workbench.config import Settings
from sovereign_workbench.core.agent.executor import StepExecutor
from sovereign_workbench.core.agent.memory import AgentMemory
from sovereign_workbench.core.agent.planner import PlanStep, TaskPlanner
from sovereign_workbench.core.agent.tools.base import ToolContext
from sovereign_workbench.core.llm.inference import run_stream
from sovereign_workbench.core.llm.provider import Capability, ChatMessage
from sovereign_workbench.core.llm.registry import ModelRegistry
from sovereign_workbench.core.llm.router import ModelRouter, NoModelAvailable
from sovereign_workbench.observability.logging import get_logger
from sovereign_workbench.schemas.events import AgentEvent, AgentEventType

log = get_logger(__name__)

ArtifactSink = Callable[[Path, str], dict[str, Any]]

_FINAL_SYSTEM = (
    "You are the final step of an on-premise industrial assistant. Using only the "
    "observations below, produce the user's deliverable or answer. If files were "
    "drafted, state their names. Be concise and concrete."
)


def _event(task_id: UUID, event_type: AgentEventType, data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(type=event_type, task_id=task_id, at=datetime.now(UTC), data=data)


class AgentLoop:
    def __init__(
        self,
        registry: ModelRegistry,
        router: ModelRouter,
        planner: TaskPlanner,
        executor: StepExecutor,
        settings: Settings,
    ) -> None:
        self.registry = registry
        self.router = router
        self.planner = planner
        self.executor = executor
        self.settings = settings

    async def run(
        self,
        task_id: UUID,
        prompt: str,
        ctx: ToolContext,
        *,
        register_artifact: ArtifactSink | None = None,
        model_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        memory = AgentMemory(prompt=prompt)
        files = sorted(path.name for path in ctx.workspace_dir.iterdir() if path.is_file())
        context = (
            f"Attached workspace files: {files}. Read source files before using their content. "
            f"Permissions: write_files={ctx.write_files}, run_code={ctx.run_code}. "
            "Office deliverable tools may produce task artifacts. "
            "Never invent observations or claim a file was created without a tool result."
        )
        requested_max_steps = ctx.extras.get("max_steps")
        max_steps = self.settings.max_agent_steps
        if isinstance(requested_max_steps, int):
            max_steps = min(max_steps, max(requested_max_steps, 1))

        yield _event(task_id, "step_start", {"title": "Planning"})
        try:
            stage: Capability = "code" if self.router.classify(prompt) == "code" else "plan"
            planning_model = self.router.route_capability(stage, model_id=model_id)
        except NoModelAvailable:
            planning_model = None
        try:
            answer_model = self.router.route_capability(
                "code" if self.router.classify(prompt) == "code" else "chat", model_id=model_id
            )
        except NoModelAvailable:
            answer_model = None
        if planning_model:
            plan = await self.planner.plan(prompt, context=context, model_id=planning_model.spec.id)
        else:
            plan = self.planner._fallback_plan(prompt)
        yield _event(
            task_id,
            "plan",
            {
                "model_id": answer_model.spec.id if answer_model else None,
                "planning_model_id": planning_model.spec.id if planning_model else None,
                "capability": answer_model.capability if answer_model else None,
                "steps": [{"title": s.title, "tool": s.tool, "kind": s.kind} for s in plan],
            },
        )

        index = 0
        replanned = False
        while plan:
            if index >= max_steps:
                raise AgentRunError("task reached its step limit", code="STEP_LIMIT")
            index += 1
            step = plan.pop(0)
            if _is_cancelled(ctx):
                raise AgentRunError("task cancelled by user", code="TASK_CANCELLED")
            yield _event(task_id, "step_start", {"index": index, "title": step.title})
            if step.kind == "tool_call" and step.tool:
                yield _event(task_id, "tool_call", {"tool": step.tool, "args": step.args})
                result = await self.executor.execute(step, ctx)
                yield _event(
                    task_id,
                    "tool_result",
                    {
                        "tool": step.tool,
                        "ok": result.ok,
                        "output": result.output[:4000],
                        "error": result.error,
                        "data": result.data,
                    },
                )
                memory.add_observation(f"[{step.title}] {result.output or result.error or ''}")
                if result.data.get("citations"):
                    memory.add_citations(result.data["citations"])
                if result.artifact_path and register_artifact:
                    artifact_kind = str(
                        result.data.get("artifact_kind", result.data.get("kind", "text"))
                    )
                    artifact = register_artifact(result.artifact_path, artifact_kind)
                    memory.add_artifact(artifact)
                    yield _event(task_id, "artifact", artifact)
                if register_artifact:
                    for path, kind in result.extra_artifacts:
                        artifact = register_artifact(path, kind)
                        memory.add_artifact(artifact)
                        yield _event(task_id, "artifact", artifact)
                if not result.ok:
                    if (
                        not replanned
                        and planning_model
                        and index < max_steps
                        and result.data.get("failure_code")
                        not in {
                            "TOOL_DENIED",
                            "OCR_NO_TEXT",
                            "OCR_INCOMPLETE",
                            "NO_SOURCE_DOCUMENT",
                        }
                    ):
                        replanned = True
                        plan = await self.planner.plan(
                            prompt,
                            context=(
                                f"{context}\nRecover from this failure. "
                                f"Do not repeat successful steps.\n{memory.context_text()}"
                            ),
                            model_id=planning_model.spec.id,
                        )
                        yield _event(
                            task_id,
                            "plan",
                            {
                                "replanned": True,
                                "steps": [
                                    {"title": s.title, "tool": s.tool, "kind": s.kind} for s in plan
                                ],
                            },
                        )
                        continue
                    raise AgentRunError(
                        result.error or f"tool {step.tool} failed",
                        code=str(result.data.get("failure_code", "TOOL_FAILED")),
                        tool=step.tool,
                    )
                if (
                    planning_model
                    and step.tool
                    in {
                        "read_file",
                        "read_document",
                        "read_spreadsheet",
                        "search_documents",
                        "describe_image",
                    }
                    and any(p.kind == "tool_call" for p in plan)
                ):
                    plan = await self.planner.plan(
                        prompt,
                        context=(
                            f"{context}\nPlan only the remaining work using these observations. "
                            f"Do not repeat completed steps.\n{memory.context_text()}"
                        ),
                        model_id=planning_model.spec.id,
                    )
            if _is_cancelled(ctx):
                raise AgentRunError("task cancelled by user", code="TASK_CANCELLED")

        yield _event(task_id, "step_start", {"title": "Writing the answer"})
        final_model_id = answer_model.spec.id if answer_model else None
        async for token in self._finalize(task_id, memory, model_id=final_model_id):
            if _is_cancelled(ctx):
                raise AgentRunError("task cancelled by user", code="TASK_CANCELLED")
            yield _event(task_id, "token", {"text": token})

        if _is_cancelled(ctx):
            raise AgentRunError("task cancelled by user", code="TASK_CANCELLED")
        yield _event(
            task_id,
            "done",
            {
                "artifacts": [a.get("filename") for a in memory.artifacts],
                "citations": memory.citations,
            },
        )

    async def _finalize(
        self,
        task_id: UUID,
        memory: AgentMemory,
        *,
        model_id: str | None = None,
    ) -> AsyncIterator[str]:
        messages = [
            ChatMessage("system", _FINAL_SYSTEM),
            ChatMessage("user", f"{memory.prompt}\n\nObservations:\n{memory.context_text()}"),
        ]
        emitted = False
        try:
            decision = self.router.route_capability("chat", model_id=model_id)
            async for token in run_stream(
                self.registry, decision.spec, messages, temperature=0.2, max_tokens=1200
            ):
                if token:
                    emitted = True
                    yield token
            if not emitted:
                raise ValueError("local model returned an empty response")
        except Exception as exc:
            log.warning("finalize failed", extra={"extra_fields": {"error": str(exc)}})
            if emitted:
                raise AgentRunError("model stream interrupted", code="MODEL_STREAM_FAILED") from exc
            if not memory.observations and not memory.artifacts:
                raise AgentRunError(
                    "no local model could produce an answer; start a local model and retry",
                    code="MODEL_UNAVAILABLE",
                ) from exc
            yield f"(model unavailable; summary) {memory.summary()}"
            return


class AgentRunError(RuntimeError):
    def __init__(
        self, message: str, *, code: str = "AGENT_FAILED", tool: str | None = None
    ) -> None:
        self.code = code
        self.tool = tool
        super().__init__(message)


def _is_cancelled(ctx: ToolContext) -> bool:
    callback = ctx.extras.get("is_cancelled")
    return bool(callback()) if callable(callback) else False


def plan_from_dicts(raw: list[dict[str, Any]]) -> list[PlanStep]:
    return [
        PlanStep(
            title=str(item.get("title", "step")),
            kind=str(item.get("kind", "tool_call" if item.get("tool") else "answer")),
            tool=item.get("tool"),
            args=item.get("args") or {},
        )
        for item in raw
    ]
