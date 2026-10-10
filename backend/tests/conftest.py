"""Test configuration.

Environment is set *before* any application import so the cached Settings picks it
up. Tests never touch the network: AIRGAP is on and remote providers are dropped.
"""

from __future__ import annotations

import os
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
