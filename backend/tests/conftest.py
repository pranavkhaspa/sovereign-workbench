"""Test configuration.

Environment is set *before* any application import so the cached Settings picks it
up. Tests never touch the network: AIRGAP is on and remote providers are dropped.
"""

from __future__ import annotations

import os
import socket
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="sw-test-"))

os.environ.update(
    {
        "AIRGAP": "true",
        "HARDWARE_TIER": "min",
        "MODEL_REGISTRY_PATH": str(ROOT / "models" / "models.toml"),
        "DATA_DIR": str(TMP / "data"),
        "WORKSPACE_DIR": str(TMP / "workspace"),
        "ARTIFACTS_DIR": str(TMP / "artifacts"),
        "UPLOADS_DIR": str(TMP / "uploads"),
        "VECTOR_STORE_DIR": str(TMP / "vectorstore"),
        "DATABASE_URL": f"sqlite:///{TMP / 'test.sqlite3'}",
    }
)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_offline_state(monkeypatch):
    from sqlalchemy import delete

    from sovereign_workbench.api.deps import _get_registry_and_router, get_task_runner
    from sovereign_workbench.core.llm import router
    from sovereign_workbench.core.llm.registry import get_registry
    from sovereign_workbench.core.rag.embeddings import reset_embedder
    from sovereign_workbench.core.sandbox.subprocess_sandbox import reset_sandbox
    from sovereign_workbench.core.security import airgap
    from sovereign_workbench.db.base import Base
    from sovereign_workbench.db.session import init_db, session_scope

    init_db()
    with session_scope() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
    get_task_runner.cache_clear()
    _get_registry_and_router.cache_clear()
    get_registry.cache_clear()
    monkeypatch.setattr(router, "_router", None)
    monkeypatch.setattr(airgap, "_guard", None)
    reset_embedder()
    reset_sandbox()

    def deny_network(*args, **kwargs):
        raise AssertionError("tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    monkeypatch.setattr(socket.socket, "sendto", deny_network)
    monkeypatch.setattr(socket, "getaddrinfo", deny_network)


@pytest.fixture
def client(monkeypatch):
    async def skip_probe(self):
        return None

    monkeypatch.setattr(
        "sovereign_workbench.core.llm.registry.ModelRegistry.refresh_availability",
        skip_probe,
    )
    from fastapi.testclient import TestClient

    from sovereign_workbench.main import app

    with TestClient(app) as test_client:
        yield test_client
