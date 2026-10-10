from __future__ import annotations

import asyncio

import pytest

from sovereign_workbench.core.llm.provider import ChatMessage, Completion, ModelProvider, ModelSpec
from sovereign_workbench.core.llm.registry import ModelRegistry
from sovereign_workbench.core.llm.router import ModelRouter, NoModelAvailable


class InstalledModels(ModelProvider):
    name = "test-provider"

    async def is_available(self) -> bool:
        return True

    async def available_models(self) -> set[str] | None:
        return {"general-installed"}

    async def chat(
        self,
        spec: ModelSpec,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        tools: list[dict[str, object]] | None = None,
    ) -> Completion:
        return Completion(text="ok", model_id=spec.id)


def test_registry_does_not_mark_uninstalled_models_available():
    general = ModelSpec(
        id="general",
        provider="test-provider",
        remote=False,
        tier="min",
        capabilities=["plan", "chat"],
        model_name="general-installed",
    )
    coder = ModelSpec(
        id="coder",
        provider="test-provider",
        remote=False,
        tier="min",
        capabilities=["code", "chat"],
        model_name="coder-not-installed",
    )
    registry = ModelRegistry([general, coder], {"test-provider": InstalledModels()}, airgap=True)
    asyncio.run(registry.refresh_availability())
    assert registry.is_available(general)
    assert not registry.is_available(coder)
    router = ModelRouter(registry)
    assert router.route("fix my Python function").spec.id == "general"
    with pytest.raises(NoModelAvailable):
        router.route("describe this scanned image", has_image=True)


def test_ollama_latest_alias_matches_registry_name(monkeypatch):
    provider = InstalledModels()

    async def available():
        return {"moondream2:latest"}

    monkeypatch.setattr(provider, "available_models", available)
    vision = ModelSpec("vision", "test-provider", False, "min", ["vision"], "moondream2")
    registry = ModelRegistry([vision], {"test-provider": provider}, airgap=True)
    asyncio.run(registry.refresh_availability())
    assert registry.is_available(vision)
