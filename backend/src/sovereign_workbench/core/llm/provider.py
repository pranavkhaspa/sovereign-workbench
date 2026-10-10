"""LLM provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]
Capability = Literal["plan", "chat", "code", "vision", "embed"]
Tier = Literal["min", "standard", "large", "remote"]


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str
    name: str | None = None
    images: list[str] = field(default_factory=list)  # data URLs or local paths


@dataclass(slots=True)
class Completion:
    text: str
    model_id: str
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class ModelSpec:
    """A registry entry. See models/models.toml."""

    id: str
    provider: str
    remote: bool
    tier: Tier
    capabilities: list[Capability]
    model_name: str
    context: int = 8192
    tags: list[str] = field(default_factory=list)
    notes: str | None = None

    def label(self) -> str:
        return self.notes or self.model_name


class ModelProvider(ABC):
    """A source of completions. Implementations must go through the egress guard."""

    name: str

    @abstractmethod
    async def is_available(self) -> bool: ...

    async def available_models(self) -> set[str] | None:
        """Return installed model IDs when the provider can enumerate them."""
        return None

    @abstractmethod
    async def chat(
        self,
        spec: ModelSpec,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> Completion: ...

    async def stream(
        self,
        spec: ModelSpec,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Default: non-streaming providers yield the whole answer at once."""
        completion = await self.chat(
            spec, messages, temperature=temperature, max_tokens=max_tokens
        )
        yield completion.text
