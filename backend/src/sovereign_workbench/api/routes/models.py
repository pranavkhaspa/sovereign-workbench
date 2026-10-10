from __future__ import annotations

from fastapi import APIRouter, HTTPException

from sovereign_workbench.core.llm.registry import get_registry
from sovereign_workbench.schemas.models import ModelInfo, ModelList

router = APIRouter(tags=["models"])


def _model_info(spec, registry) -> ModelInfo:
    return ModelInfo(
        id=spec.id,
        label=spec.label(),
        provider=spec.provider,
        remote=spec.remote,
        tier=spec.tier,
        capabilities=spec.capabilities,
        available=registry.is_available(spec),
        size_hint=next((t for t in spec.tags if t.endswith("b") or "gb" in t), None),
        notes=spec.notes,
    )


@router.get("/models", response_model=ModelList)
async def list_models() -> ModelList:
    registry = get_registry()
    models = [_model_info(spec, registry) for spec in registry.all()]
    return ModelList(models=models)


@router.get("/models/{model_id}", response_model=ModelInfo)
async def get_model(model_id: str) -> ModelInfo:
    registry = get_registry()
    spec = registry.get(model_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="model not found")
    return _model_info(spec, registry)


@router.post("/models/refresh", response_model=ModelList)
async def refresh_models() -> ModelList:
    await get_registry().refresh_availability()
    return await list_models()
