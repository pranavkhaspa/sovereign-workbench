from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

AgentEventType = Literal[
    "plan",
    "step_start",
    "tool_call",
    "tool_result",
    "token",
    "artifact",
    "done",
    "error",
]


class AgentEvent(BaseModel):
    id: int | None = None
    type: AgentEventType
    task_id: UUID
    at: datetime
    data: dict[str, Any] = {}
