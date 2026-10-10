from __future__ import annotations

import asyncio
from pathlib import Path

from sovereign_workbench.config import get_settings
from sovereign_workbench.core.agent.tools.base import ToolContext
from sovereign_workbench.core.agent.tools.fs_tools import (
    ListFilesArgs,
    ListFilesTool,
    ReadFileArgs,
    ReadFileTool,
    WriteFileArgs,
    WriteFileTool,
)


def _ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        workspace_dir=tmp_path,
        artifacts_dir=tmp_path / "artifacts",
        settings=get_settings(),
        write_files=True,
    )


def test_write_then_read_roundtrip(tmp_path):
    ctx = _ctx(tmp_path)
    write = asyncio.run(
        WriteFileTool().run(WriteFileArgs(path="notes/a.txt", content="hello"), ctx)
    )
    assert write.ok
    read = asyncio.run(ReadFileTool().run(ReadFileArgs(path="notes/a.txt"), ctx))
    assert read.ok
    assert read.output == "hello"


def test_list_files(tmp_path):
    (tmp_path / "one.txt").write_text("x")
    ctx = _ctx(tmp_path)
    result = asyncio.run(ListFilesTool().run(ListFilesArgs(), ctx))
    assert result.ok
    assert "one.txt" in result.output


def test_path_escape_is_refused(tmp_path):
    ctx = _ctx(tmp_path)
    result = asyncio.run(ReadFileTool().run(ReadFileArgs(path="../../etc/passwd"), ctx))
    assert not result.ok
    assert "escapes workspace" in (result.error or "")


def test_write_denied_without_permission(tmp_path):
    ctx = ToolContext(
        workspace_dir=tmp_path,
        artifacts_dir=tmp_path / "artifacts",
        settings=get_settings(),
        write_files=False,
    )
    permitted, reason = WriteFileTool().is_permitted(ctx)
    assert not permitted
    assert reason is not None
