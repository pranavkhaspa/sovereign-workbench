from __future__ import annotations

from typing import Any

from sovereign_workbench.core.agent.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.json_schema() for tool in self._tools.values()]

    def describe(self) -> str:
        return "\n".join(f"- {t.name}: {t.description}" for t in self._tools.values())


def build_default_registry() -> ToolRegistry:
    """Register the built-in tools."""
    from sovereign_workbench.core.agent.tools.approval_note import CreateApprovalNoteTool
    from sovereign_workbench.core.agent.tools.code_exec import RunPythonTool
    from sovereign_workbench.core.agent.tools.doc_search import SearchDocumentsTool
    from sovereign_workbench.core.agent.tools.fs_tools import (
        ListFilesTool,
        ReadFileTool,
        WriteFileTool,
    )
    from sovereign_workbench.core.agent.tools.ocr_vision import DescribeImageTool
    from sovereign_workbench.core.agent.tools.spreadsheet import ReadSpreadsheetTool

    registry = ToolRegistry()
    for tool in (
        ListFilesTool(),
        ReadFileTool(),
        WriteFileTool(),
        RunPythonTool(),
        ReadSpreadsheetTool(),
        SearchDocumentsTool(),
        DescribeImageTool(),
        CreateApprovalNoteTool(),
    ):
        registry.register(tool)
    return registry
