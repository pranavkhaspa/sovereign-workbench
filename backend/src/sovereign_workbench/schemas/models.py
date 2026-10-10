from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["min", "standard", "large", "remote"]
Capability = Literal["plan", "chat", "code", "vision", "embed"]


class ModelInfo(BaseModel):
    id: str
    label: str
    provider: str
    remote: bool
    tier: Tier
    capabilities: list[Capability]
    available: bool = False
    size_hint: str | None = None
    notes: str | None = None


class ModelList(BaseModel):
    models: list[ModelInfo] = Field(default_factory=list)
