"""Thin inference helper — the only place feature code calls a provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from sovereign_workbench.config import get_settings
from sovereign_workbench.core.llm.provider import ChatMessage, Completion, ModelSpec
from sovereign_workbench.core.llm.registry import ModelRegistry
from sovereign_workbench.core.security.airgap import EgressBlocked
from sovereign_workbench.core.security.audit import get_audit_log


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
    if registry.airgap and spec.remote:
        raise EgressBlocked(spec.provider)
    ranks = {"min": 0, "standard": 1, "large": 2, "remote": 3}
    ceiling = ranks[get_settings().hardware_tier]
    capability = "vision" if any(m.images for m in messages) else spec.capabilities[0]
    alternatives = [
        candidate
        for candidate in registry.candidates(capability)
        if candidate.id != spec.id
        and registry.is_available(candidate)
        and not (registry.airgap and candidate.remote)
        and (candidate.remote or ranks[candidate.tier] <= ceiling)
    ]
    alternatives.sort(key=lambda candidate: (candidate.remote, -ranks[candidate.tier]))
    for index, candidate in enumerate([spec, *alternatives[:1]]):
        provider = registry.provider_for(candidate)
        if provider is None:
            raise NoProviderError(candidate.provider)
        try:
            completion = await provider.chat(
                candidate, messages, temperature=temperature, max_tokens=max_tokens, tools=tools
            )
            if index:
                get_audit_log().record("model_fallback", data={"from": spec.id, "to": candidate.id})
            return completion
        except (httpx.HTTPError, OSError):
            get_audit_log().record("model_failed", data={"model": candidate.id})
            if index or not alternatives:
                raise
    raise NoProviderError(spec.provider)


async def run_stream(
    registry: ModelRegistry,
    spec: ModelSpec,
    messages: list[ChatMessage],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    if registry.airgap and spec.remote:
        raise EgressBlocked(spec.provider)
    provider = registry.provider_for(spec)
    if provider is None:
        raise NoProviderError(spec.provider)
    async for text in provider.stream(
        spec, messages, temperature=temperature, max_tokens=max_tokens
    ):
        yield text
