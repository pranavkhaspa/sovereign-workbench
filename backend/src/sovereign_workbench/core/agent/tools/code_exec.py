"""Sandboxed code execution tool."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field

from sovereign_workbench.core.agent.tools.base import Tool, ToolContext, ToolResult


class RunPythonArgs(BaseModel):
    code: str = Field(description="Python source to execute in the sandbox.", max_length=50_000)
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class RunPythonTool(Tool):
    name = "run_python"
    description = (
        "Execute Python code in an isolated sandbox with no network access, and return "
        "stdout, stderr and the exit code. Use for calculations and internal tooling."
    )
    args_schema = RunPythonArgs
    requires_code = True

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, RunPythonArgs)
        if ctx.sandbox is None:
            return ToolResult(ok=False, error="no sandbox available")
        try:
            result = await ctx.sandbox.run(
                args.code,
                language="python",
                timeout_s=min(args.timeout_seconds, ctx.settings.tool_timeout_seconds),
            )
            code_path = ctx.workspace_dir / "executed_code.py"
            if code_path.exists():
                code_path = ctx.workspace_dir / f"executed_code_{uuid4().hex[:8]}.py"
            code_path.write_text(args.code, encoding="utf-8")
            output = (
                f"exit={result.exit_code}\n--- stdout ---\n{result.stdout}"
                f"\n--- stderr ---\n{result.stderr}\ntimed_out={result.timed_out}"
            )
            log_path = code_path.with_suffix(".log")
            log_path.write_text(output, encoding="utf-8")
            return ToolResult(
                ok=result.exit_code == 0 and not result.timed_out,
                output=output,
                data={
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "artifact_kind": "code",
                },
                artifact_path=code_path,
                extra_artifacts=[(log_path, "log")],
                error=(
                    "sandbox timed out"
                    if result.timed_out
                    else None if result.exit_code == 0 else result.stderr[:500]
                ),
            )
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))
