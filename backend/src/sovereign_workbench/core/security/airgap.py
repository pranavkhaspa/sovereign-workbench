"""Egress guard — the single choke point for outbound network access.

In air-gap mode, only loopback and private-range hosts are reachable. Every other
attempt raises :class:`EgressBlocked` and is counted (and, by callers, audited).
This is what makes the "no external calls" claim verifiable rather than asserted.

`get_client()` returns an ``httpx.AsyncClient`` whose transport enforces the guard,
so feature code physically cannot bypass it without avoiding this helper (which a
unit test enforces).
"""

from __future__ import annotations

import ipaddress
import threading
from urllib.parse import urlparse

import httpx

from sovereign_workbench.config import get_settings
from sovereign_workbench.observability.logging import get_logger

log = get_logger(__name__)

_LOCAL_HOSTNAMES = {"localhost", "host.docker.internal"}
_PRIVATE_V4 = tuple(
    ipaddress.ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
_PRIVATE_V6 = ipaddress.ip_network("fc00::/7")


class EgressBlocked(RuntimeError):
    """Raised when an outbound request is not permitted by the current mode."""

    def __init__(self, host: str, reason: str = "air-gap") -> None:
        self.host = host
        self.reason = reason
        super().__init__(f"Egress to {host!r} blocked ({reason})")


def _is_local_host(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() in _LOCAL_HOSTNAMES:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # A DNS name that is not obviously local is treated as external.
        return False
    if ip.is_loopback or ip.is_link_local:
        return True
    if isinstance(ip, ipaddress.IPv4Address):
        return any(ip in network for network in _PRIVATE_V4)
    return ip in _PRIVATE_V6


class EgressGuard:
    def __init__(self, airgap: bool) -> None:
        self.airgap = airgap
        self._lock = threading.Lock()
        self._blocked = 0
        self._allowed_local = 0
        self._external_allowed = 0
        self._local_endpoints: set[str] = set()

    def check(self, url: str) -> None:
        """Raise if the URL may not be reached; otherwise record it."""
        host = urlparse(url).hostname
        local = _is_local_host(host)
        with self._lock:
            if local:
                self._allowed_local += 1
                if host:
                    self._local_endpoints.add(f"{host}:{urlparse(url).port or ''}".rstrip(":"))
                return
            if self.airgap:
                self._blocked += 1
            else:
                self._external_allowed += 1
        if self.airgap and not local:
            from sovereign_workbench.core.security.audit import get_audit_log

            get_audit_log().record(
                "egress_blocked",
                actor="egress-guard",
                detail=f"Blocked outbound request to {host}",
                data={"host": host, "url": url},
            )
            raise EgressBlocked(host or "<unknown>")

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "airgap": self.airgap,
                "blocked": self._blocked,
                "allowed_local": self._allowed_local,
                "external_allowed": self._external_allowed,
                "local_endpoints": sorted(self._local_endpoints),
            }


_guard: EgressGuard | None = None


def get_egress_guard() -> EgressGuard:
    global _guard
    if _guard is None:
        _guard = EgressGuard(airgap=get_settings().airgap)
    return _guard


class _GuardedTransport(httpx.AsyncHTTPTransport):
    """httpx transport that enforces the guard before any connection is opened."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        get_egress_guard().check(str(request.url))
        return await super().handle_async_request(request)


def get_client(*, timeout: float = 60.0) -> httpx.AsyncClient:
    """The only sanctioned way to make outbound HTTP calls."""
    return httpx.AsyncClient(transport=_GuardedTransport(), timeout=timeout)
