from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditEvent(BaseModel):
    id: UUID
    type: str  # egress_blocked | egress_allowed_local | tool_call | model_selected | ...
    actor: str
    detail: str
    data: dict[str, Any] | None = None
    created_at: datetime


class EgressStatus(BaseModel):
    airgap: bool
    blocked: int
    allowed_local: int
    external_allowed: int
    local_endpoints: list[str]
