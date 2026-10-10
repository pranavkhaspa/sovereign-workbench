"""FastAPI application entrypoint."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from sovereign_workbench import __version__
from sovereign_workbench.api import api_router
from sovereign_workbench.api.deps import get_task_runner
from sovereign_workbench.config import get_settings
from sovereign_workbench.core.llm.registry import get_registry
from sovereign_workbench.core.security.audit import get_audit_log
from sovereign_workbench.db.session import init_db
from sovereign_workbench.observability.logging import configure_logging, get_logger

log = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_dirs()
    init_db()
    get_task_runner().recover_interrupted()
    get_audit_log().record("app_started", actor="system", detail=f"version {__version__}")
    try:
        await get_registry().refresh_availability()
    except Exception as exc:
        log.warning("model probe failed at startup", extra={"extra_fields": {"error": str(exc)}})
    log.info(
        "sovereign workbench ready",
        extra={"extra_fields": {"airgap": settings.airgap, "tier": settings.hardware_tier}},
    )
    try:
        yield
    finally:
        await get_task_runner().shutdown()
        get_audit_log().record("app_stopped", actor="system", detail="shutdown")


def create_app() -> FastAPI:
    get_settings()
    app = FastAPI(
        title="Sovereign Workbench",
        description="Self-hosted, air-gapped agentic AI workbench.",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            error = detail
        else:
            error = {"code": f"http_{exc.status_code}", "message": str(detail)}
        return JSONResponse(
            status_code=exc.status_code, content={"error": error}, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "request validation failed",
                    "details": [
                        {"loc": list(error["loc"]), "message": str(error["msg"])}
                        for error in exc.errors()
                    ],
                }
            },
        )

    app.include_router(api_router)
    return app


app = create_app()
