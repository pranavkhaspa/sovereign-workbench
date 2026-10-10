from __future__ import annotations

import pytest

from sovereign_workbench.core.security.airgap import EgressBlocked, EgressGuard


def test_blocked_egress_is_counted_and_audited(client, monkeypatch):
    guard = EgressGuard(airgap=True)
    monkeypatch.setattr("sovereign_workbench.core.security.airgap._guard", guard)
    with pytest.raises(EgressBlocked):
        guard.check("https://api.example.com/v1/completions")
    status = client.get("/api/audit/egress")
    assert status.status_code == 200
    assert status.json()["blocked"] == 1
    assert status.json()["external_allowed"] == 0
    audit = client.get("/api/audit", params={"type": "egress_blocked"})
    assert audit.status_code == 200
    assert any(event["data"]["host"] == "api.example.com" for event in audit.json())


def test_egress_totals_survive_guard_restart(client, monkeypatch):
    from sovereign_workbench.core.security.airgap import get_egress_guard

    with pytest.raises(EgressBlocked):
        get_egress_guard().check("https://example.com/")
    monkeypatch.setattr("sovereign_workbench.core.security.airgap._guard", None)
    assert client.get("/api/audit/egress").json()["blocked"] == 1
