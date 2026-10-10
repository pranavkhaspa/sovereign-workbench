"""Thin inference helper — the only place feature code calls a provider."""

from __future__ import annotations

from typing import Any

from sovereign_workbench.core.llm.provider import ChatMessage, Completion, ModelSpec
from sovereign_workbench.core.llm.registry import ModelRegistry


class NoProviderError(RuntimeError):
    def __init__(self, provider: str) -> None:
        super().__init__(f"no provider configured for {provider!r}")


async def run_chat(
    registry: ModelRegistry,
    spec: ModelSpec,
    messages: list[ChatMessage],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> Completion:
    provider = registry.provider_for(spec)
    if provider is None:
        raise NoProviderError(spec.provider)
    return await provider.chat(
        spec, messages, temperature=temperature, max_tokens=max_tokens, tools=tools
    )
