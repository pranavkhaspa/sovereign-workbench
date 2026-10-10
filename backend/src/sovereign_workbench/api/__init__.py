from fastapi import APIRouter

from sovereign_workbench.api.routes import artifacts, audit, chat, documents, health, models, tasks

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(models.router)
api_router.include_router(chat.router)
api_router.include_router(tasks.router)
api_router.include_router(documents.router)
api_router.include_router(artifacts.router)
api_router.include_router(audit.router)

__all__ = ["api_router"]
