from __future__ import annotations

from sovereign_workbench.core.llm.registry import get_registry
from sovereign_workbench.core.llm.router import ModelRouter


def test_registry_drops_remote_models_in_airgap():
    registry = get_registry()
    assert registry.all()
    assert all(not spec.remote for spec in registry.all())


def test_router_classifies_code():
    router = ModelRouter(get_registry(), tier="min")
    assert router.classify("fix this python traceback") == "code"


def test_router_classifies_vision():
    router = ModelRouter(get_registry(), tier="min")
    assert router.classify("read this scanned drawing") == "vision"
    assert router.classify("anything", has_image=True) == "vision"


def test_router_defaults_to_chat():
    router = ModelRouter(get_registry(), tier="min")
    assert router.classify("summarise this for me") == "chat"


def test_route_selects_a_capable_model():
    router = ModelRouter(get_registry(), tier="min")
    decision = router.route("write a python function to parse a csv")
    assert "code" in decision.spec.capabilities


def test_route_switches_between_code_and_general_tasks():
    router = ModelRouter(get_registry(), tier="min")
    code = router.route("fix this Python function").spec
    summary = router.route("summarise this inspection report").spec
    assert code.id == "coder-min"
    assert summary.id != code.id


def test_router_uses_larger_tier_without_exceeding_ceiling(monkeypatch):
    import pytest

    from sovereign_workbench.core.llm.router import NoModelAvailable

    registry = get_registry()
    assert ModelRouter(registry, tier="large").route("Write python code").spec.id == "coder-large"
    monkeypatch.setattr(registry, "probed", True)
    monkeypatch.setattr(registry, "_available", {"coder-large": True})
    with pytest.raises(NoModelAvailable):
        ModelRouter(registry, tier="min").route("Write python code")
