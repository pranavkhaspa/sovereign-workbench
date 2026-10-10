"""Tool abstraction.

Every capability the agent can use is a :class:`Tool`. Tools declare a Pydantic
``args_schema`` (turned into JSON schema for the model) and run inside a
:class:`ToolContext` that carries the workspace, sandbox and options.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from uuid import UUID

    from sovereign_workbench.config import Settings
    from sovereign_workbench.core.sandbox.base import Sandbox


@dataclass
class ToolContext:
    workspace_dir: Path
    artifacts_dir: Path
    settings: "Settings"
    task_id: "UUID | None" = None
    allow_network: bool = False
    write_files: bool = False
    run_code: bool = False
    sandbox: "Sandbox | None" = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    output: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    artifact_path: Path | None = None
    error: str | None = None


class Tool(ABC):
    name: str
    description: str
    args_schema: type[BaseModel]
    requires_network: bool = False
    requires_write: bool = False
    requires_code: bool = False

    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def is_permitted(self, ctx: ToolContext) -> tuple[bool, str | None]:
        if self.requires_network and not ctx.allow_network:
            return False, "tool requires network but network is not permitted for this task"
        if self.requires_write and not ctx.write_files:
            return False, "tool writes files but file writes are not permitted for this task"
        if self.requires_code and not ctx.run_code:
            return False, "tool runs code but code execution is not permitted for this task"
        return True, None

    @abstractmethod
    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult: ...
