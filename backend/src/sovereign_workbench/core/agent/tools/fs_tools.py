"""Filesystem tools, jailed to the task workspace."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from sovereign_workbench.core.agent.tools.base import Tool, ToolContext, ToolResult

_MAX_READ = 40_000


def _safe_path(ctx: ToolContext, relative: str) -> Path:
    base = ctx.workspace_dir.resolve()
    candidate = (base / relative).resolve()
    if base not in candidate.parents and candidate != base:
        raise ValueError(f"path escapes workspace: {relative}")
    return candidate


class ListFilesArgs(BaseModel):
    path: str = Field(default=".", description="Directory relative to the workspace.")


class ListFilesTool(Tool):
    name = "list_files"
    description = "List files in a workspace directory. Use to discover available documents."
    args_schema = ListFilesArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, ListFilesArgs)
        try:
            target = _safe_path(ctx, args.path)
            if not target.exists():
                return ToolResult(ok=False, error=f"not found: {args.path}")
            entries = sorted(f"{p.name}/" if p.is_dir() else p.name for p in target.iterdir())
            return ToolResult(
                ok=True, output="\n".join(entries) or "(empty)", data={"count": len(entries)}
            )
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class ReadFileArgs(BaseModel):
    path: str = Field(description="File path relative to the workspace.")
    max_chars: int = Field(default=20000, ge=1, le=_MAX_READ)


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a UTF-8 text file from the workspace."
    args_schema = ReadFileArgs

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, ReadFileArgs)
        try:
            target = _safe_path(ctx, args.path)
            text = target.read_text(encoding="utf-8", errors="replace")
            clipped = text[: args.max_chars]
            return ToolResult(
                ok=True,
                output=clipped,
                data={"path": str(target), "truncated": len(text) > len(clipped)},
            )
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))


class WriteFileArgs(BaseModel):
    path: str = Field(description="Destination path relative to the workspace.")
    content: str = Field(description="Full file content to write.")


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write a text file into the workspace. Requires file-write permission."
    args_schema = WriteFileArgs
    requires_write = True

    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult:
        assert isinstance(args, WriteFileArgs)
        try:
            target = _safe_path(ctx, args.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(args.content, encoding="utf-8")
            return ToolResult(
                ok=True,
                output=f"wrote {len(args.content)} chars to {args.path}",
                artifact_path=target,
                data={
                    "artifact_kind": (
                        "code" if target.suffix in {".py", ".js", ".ts", ".sql"} else "text"
                    )
                },
            )
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))
