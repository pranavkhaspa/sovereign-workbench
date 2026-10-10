from __future__ import annotations

from pydantic import BaseModel, Field

from sovereign_workbench.core.agent.tools.base import Tool, ToolContext, ToolResult
from sovereign_workbench.core.deliverables.calculations import calculate


class CalculateArgs(BaseModel):
    expression: str = Field(min_length=1, max_length=2000)


class CalculateTool(Tool):
    name = "calculate"
    description = "Evaluate arithmetic (+, -, *, /, **, %) and show intermediate steps."
    args_schema = CalculateArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, CalculateArgs)
        result, steps = calculate(args.expression)
        return ToolResult(ok=True, output="\n".join(steps), data={"result": result, "steps": steps})
