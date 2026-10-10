"""Capability router — chooses a model per task.

This is the mechanism behind "model auto-selection across at least two task types".
The router classifies the task, then picks the best *available* model that declares
the needed capability, within the configured hardware tier.
"""

from __future__ import annotations

from dataclasses import dataclass

from sovereign_workbench.config import get_settings
from sovereign_workbench.core.llm.provider import Capability, ModelSpec
from sovereign_workbench.core.llm.registry import ModelRegistry, get_registry
from sovereign_workbench.core.security.audit import get_audit_log
from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)

_TIER_RANK = {"min": 0, "standard": 1, "large": 2, "remote": 3}

_CODE_HINTS = (
    "code", "function", "script", "bug", "traceback", "compile", "python", "javascript",
    "typescript", "sql", "regex", "refactor", "unit test", "error", "stack trace",
)
_VISION_HINTS = (
    "image", "photo", "drawing", "diagram", "scan", "scanned", "p&id", "blueprint",
    "handwritten", "figure", "screenshot",
)

_FALLBACK: dict[Capability, list[Capability]] = {
    "code": ["code", "chat", "plan"],
    "vision": ["vision"],
    "plan": ["plan", "chat"],
    "chat": ["chat", "plan"],
    "embed": ["embed"],
}


@dataclass(slots=True)
class RouteDecision:
    spec: ModelSpec
    capability: Capability
    reason: str


class ModelRouter:
    def __init__(self, registry: ModelRegistry, tier: str = "min") -> None:
        self.registry = registry
        self.tier = tier
        self._ceiling = _TIER_RANK.get(tier, 0)

    def classify(self, text: str, *, has_image: bool = False) -> Capability:
        if has_image:
            return "vision"
        lowered = text.lower()
        if any(hint in lowered for hint in _VISION_HINTS):
            return "vision"
        if any(hint in lowered for hint in _CODE_HINTS):
            return "code"
        return "chat"

    def route(
        self,
        text: str,
        *,
        has_image: bool = False,
        model_id: str | None = None,
    ) -> RouteDecision:
        if model_id:
            spec = self.registry.get(model_id)
            if spec is not None:
                return RouteDecision(spec, self._capability_for(spec), "explicit selection")
        capability = self.classify(text, has_image=has_image)
        decision = self._pick(capability)
        get_audit_log().record(
            "model_selected",
            detail=f"{capability} -> {decision.spec.id} ({decision.reason})",
            data={"capability": capability, "model": decision.spec.id, "tier": self.tier},
        )
        return decision

    def route_capability(
        self,
        capability: Capability,
        *,
        model_id: str | None = None,
    ) -> RouteDecision:
        """Choose a model for an agent stage without guessing from its prompt."""
        if model_id:
            spec = self.registry.get(model_id)
            if spec is not None and capability in spec.capabilities:
                return RouteDecision(spec, capability, "explicit selection")
        decision = self._pick(capability)
        get_audit_log().record(
            "model_selected",
            detail=f"{capability} -> {decision.spec.id} ({decision.reason})",
            data={"capability": capability, "model": decision.spec.id, "tier": self.tier},
        )
        return decision

    def _pick(self, capability: Capability) -> RouteDecision:
        for candidate in _FALLBACK.get(capability, [capability]):
            spec = self._best_for(candidate, strict=True)
            if spec is not None:
                return RouteDecision(spec, capability, f"{capability} within tier {self.tier}")
        for candidate in _FALLBACK.get(capability, [capability]):
            spec = self._best_for(candidate, strict=False)
            if spec is not None:
                return RouteDecision(spec, capability, f"{capability} (widened past tier)")
        raise NoModelAvailable(capability)

    def _best_for(self, capability: Capability, *, strict: bool) -> ModelSpec | None:
        pool = [s for s in self.registry.candidates(capability) if self.registry.is_available(s)]
        if not pool and not self.registry.probed:
            # If nothing has been probed yet, optimistically consider declared models.
            pool = self.registry.candidates(capability)
        if strict:
            pool = [s for s in pool if _TIER_RANK.get(s.tier, 0) <= self._ceiling]
        if not pool:
            return None
        return min(pool, key=lambda s: _TIER_RANK.get(s.tier, 0))

    @staticmethod
    def _capability_for(spec: ModelSpec) -> Capability:
        for cap in ("code", "vision", "plan", "chat"):
            if cap in spec.capabilities:
                return cap
        return "chat"


class NoModelAvailable(RuntimeError):
    def __init__(self, capability: str) -> None:
        self.capability = capability
        super().__init__(f"No available model for capability {capability!r}")


_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        settings = get_settings()
        _router = ModelRouter(get_registry(), tier=settings.hardware_tier)
    return _router
