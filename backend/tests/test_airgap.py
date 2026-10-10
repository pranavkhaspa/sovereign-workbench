from __future__ import annotations

import pytest

from sovereign_workbench.core.security.airgap import EgressBlocked, EgressGuard


def test_blocks_external_when_airgapped():
    guard = EgressGuard(airgap=True)
    with pytest.raises(EgressBlocked):
        guard.check("https://api.openai.com/v1/chat/completions")
    assert guard.status()["blocked"] == 1


def test_allows_loopback_when_airgapped():
    guard = EgressGuard(airgap=True)
    guard.check("http://127.0.0.1:11434/v1/models")
    guard.check("http://localhost:8080/health")
    status = guard.status()
    assert status["blocked"] == 0
    assert status["allowed_local"] == 2


def test_allows_external_when_not_airgapped():
    guard = EgressGuard(airgap=False)
    guard.check("https://example.com/")
    assert guard.status()["external_allowed"] == 1
    assert guard.status()["blocked"] == 0


@pytest.mark.parametrize(
    "url",
    [
        "https://203.0.113.2/resource",
        "http://0.0.0.0:11434/v1/models",
        "https://api.example.com/",
        "file:///tmp/secret",
    ],
)
def test_denies_non_local_and_hostless_urls(url):
    guard = EgressGuard(airgap=True)
    with pytest.raises(EgressBlocked):
        guard.check(url)
    assert guard.status()["blocked"] == 1
