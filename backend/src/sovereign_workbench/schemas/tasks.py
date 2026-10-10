from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from sovereign_workbench.schemas.artifacts import Artifact


class TaskOptions(BaseModel):
    allow_network: bool = False
    write_files: bool = False
    run_code: bool = False
    max_steps: int | None = Field(default=None, ge=1, le=100)


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    attachments: list[str] = Field(default_factory=list, max_length=8)  # document ids
    model_id: str | None = None
    options: TaskOptions = Field(default_factory=TaskOptions)

    @field_validator("prompt")
    @classmethod
    def prompt_must_contain_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value


class TaskStep(BaseModel):
    index: int
    kind: str  # plan | tool_call | observation | reflection
    title: str
    detail: str | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    ok: bool | None = None


class Task(BaseModel):
    id: UUID
    prompt: str
    status: str  # queued | running | done | error | cancelled
    model_id: str | None = None
    created_at: datetime
    updated_at: datetime
    attachments: list[str] = Field(default_factory=list)
    steps: list[TaskStep] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    error: str | None = None
