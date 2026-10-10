"""Model registry — loads `models/models.toml` and builds providers.

Adding a model is a data change (a TOML row), not a code change. Remote providers are
removed entirely when the app is in air-gap mode, so there is nothing to call.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from sovereign_workbench.config import Settings, get_settings
from sovereign_workbench.core.llm.provider import Capability, ModelProvider, ModelSpec
from sovereign_workbench.core.llm.providers.llamacpp import LlamaCppProvider
from sovereign_workbench.core.llm.providers.openai_compatible import OpenAICompatibleProvider
from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)


class ModelRegistry:
    def __init__(
        self,
        specs: list[ModelSpec],
        providers: dict[str, ModelProvider],
        *,
        airgap: bool,
    ) -> None:
        self._specs = {spec.id: spec for spec in specs}
        if len(self._specs) != len(specs):
            raise ValueError("duplicate model ID in registry")
        self._providers = providers
        self.airgap = airgap
        self._available: dict[str, bool] = {spec.id: False for spec in specs}
        self.probed = False

    # -- construction -------------------------------------------------------
    @classmethod
    def load(cls, settings: Settings | None = None, path: Path | None = None) -> ModelRegistry:
        settings = settings or get_settings()
        path = path or settings.model_registry_path
        registry_path = _resolve_registry_path(Path(path))
        raw = tomllib.loads(registry_path.read_text(encoding="utf-8"))
        specs = [ModelSpec(**entry) for entry in raw.get("model", [])]
        if settings.airgap:
            specs = [s for s in specs if not s.remote]
        providers = _build_providers(specs, settings)
        return cls(specs, providers, airgap=settings.airgap)

    # -- queries ------------------------------------------------------------
    def all(self) -> list[ModelSpec]:
        return list(self._specs.values())

    def get(self, model_id: str) -> ModelSpec | None:
        return self._specs.get(model_id)

    def provider_for(self, spec: ModelSpec) -> ModelProvider | None:
        return self._providers.get(spec.provider)

    def is_available(self, spec: ModelSpec) -> bool:
        return self._available.get(spec.id, False)

    def candidates(self, capability: Capability) -> list[ModelSpec]:
        return [spec for spec in self._specs.values() if capability in spec.capabilities]

    # -- lifecycle ----------------------------------------------------------
    async def refresh_availability(self) -> None:
        """Probe each distinct provider once and check the installed model list."""
        provider_state: dict[str, bool] = {}
        installed: dict[str, set[str] | None] = {}
        for spec in self._specs.values():
            provider = self._providers.get(spec.provider)
            if provider is None:
                from sovereign_workbench.core.rag.embeddings import is_model_loaded

                self._available[spec.id] = spec.provider == "local" and is_model_loaded(
                    spec.model_name
                )
                continue
            if spec.provider not in provider_state:
                try:
                    models = await provider.available_models()
                    state = models is not None or await provider.is_available()
                except Exception:
                    models, state = None, False
                installed[spec.provider] = models
                provider_state[spec.provider] = state
            models = installed[spec.provider]
            self._available[spec.id] = provider_state[spec.provider] and (
                models is None
                or spec.model_name in models
                or any(name.removesuffix(":latest") == spec.model_name for name in models)
            )
        self.probed = True
        log.info(
            "model availability refreshed",
            extra={"extra_fields": {"available": self._available, "airgap": self.airgap}},
        )


def _build_providers(specs: list[ModelSpec], settings: Settings) -> dict[str, ModelProvider]:
    needed = {spec.provider for spec in specs}
    providers: dict[str, ModelProvider] = {}
    if "ollama" in needed:
        providers["ollama"] = OpenAICompatibleProvider(
            "ollama", f"{settings.ollama_base_url.rstrip('/')}/v1"
        )
    if "llamacpp" in needed:
        providers["llamacpp"] = LlamaCppProvider(f"{settings.llamacpp_base_url.rstrip('/')}/v1")
    if "openai" in needed and not settings.airgap and settings.openai_api_key:
        providers["openai"] = OpenAICompatibleProvider(
            "openai", "https://api.openai.com/v1", api_key=settings.openai_api_key
        )
    if "openrouter" in needed and not settings.airgap and settings.openrouter_api_key:
        providers["openrouter"] = OpenAICompatibleProvider(
            "openrouter", "https://openrouter.ai/api/v1", api_key=settings.openrouter_api_key
        )
    # anthropic/gemini are not OpenAI-compatible; add dedicated adapters later.
    return providers


def _resolve_registry_path(path: Path) -> Path:
    if path.exists():
        return path
    if not path.is_absolute():
        for parent in Path(__file__).resolve().parents:
            candidate = parent / path
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"model registry not found: {path}")


@lru_cache
def get_registry() -> ModelRegistry:
    return ModelRegistry.load()
