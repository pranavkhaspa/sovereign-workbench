from __future__ import annotations

from fastapi import APIRouter

from sovereign_workbench import __version__
from sovereign_workbench.config import get_settings
from sovereign_workbench.core.llm.registry import get_registry
from sovereign_workbench.core.security.airgap import get_egress_guard
from sovereign_workbench.schemas.audit import EgressStatus

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    registry = get_registry()
    return {
        "status": "ok",
        "version": __version__,
        "airgap": settings.airgap,
        "hardware_tier": settings.hardware_tier,
        "models": len(registry.all()),
        "models_ready": any(
            registry.is_available(spec)
            and bool({"plan", "chat", "code", "vision"}.intersection(spec.capabilities))
            for spec in registry.all()
        ),
    }


@router.get("/health/egress", response_model=EgressStatus)
async def egress_status() -> EgressStatus:
    status = get_egress_guard().status()
    return EgressStatus(**status)  # type: ignore[arg-type]
