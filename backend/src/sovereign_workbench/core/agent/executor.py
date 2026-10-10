"""Step executor — validates a plan step and dispatches it to a tool."""

from __future__ import annotations

from pydantic import ValidationError

from sovereign_workbench.core.agent.planner import PlanStep
from sovereign_workbench.core.agent.tools.base import ToolContext, ToolResult
from sovereign_workbench.core.agent.tools.registry import ToolRegistry
from sovereign_workbench.core.security.audit import get_audit_log
from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)


class StepExecutor:
    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    async def execute(self, step: PlanStep, ctx: ToolContext) -> ToolResult:
        if not step.tool:
            return ToolResult(ok=False, error="step has no tool")
        tool = self.tools.get(step.tool)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool: {step.tool}")

        permitted, reason = tool.is_permitted(ctx)
        if not permitted:
            get_audit_log().record(
                "tool_denied",
                detail=f"{tool.name} denied: {reason}",
                data={"tool": tool.name, "reason": reason},
            )
            return ToolResult(ok=False, error=reason or "not permitted")

        try:
            args = tool.args_schema(**step.args)
        except ValidationError as exc:
            return ToolResult(ok=False, error=f"invalid arguments: {exc.errors()}")

        get_audit_log().record(
            "tool_call", detail=f"called {tool.name}", data={"tool": tool.name, "args": step.args}
        )
        return await tool.run(args, ctx)
