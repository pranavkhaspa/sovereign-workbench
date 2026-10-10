# Sovereignty — how we prove it

The PS is blunt: showing “no external calls” through logs or a network monitor *is the
actual proof of the sovereign claim, not just a statement of it.* This document is how
we make that claim verifiable.

## Layers of defence

1. **Application choke point.** The backend's provider HTTP clients go through
   `core/security/airgap.py::EgressGuard`; code bypassing that helper is not covered
   by its audit counters. Keep local network checks as a separate guardrail.
2. **Mode.** With `AIRGAP=true` (default), the guard permits only loopback
   (`127.0.0.0/8`, `::1`) and private ranges (`10/8`, `172.16/12`, `192.168/16`) — i.e.
   the local model server and local databases. Everything else raises `EgressBlocked`
   and is recorded.
3. **Remote providers removed.** The model registry marks `provider=openai|openrouter|
   anthropic|gemini` as `remote`; the router drops remote models entirely in air-gap
   mode, so there is nothing to call even if code tried.
4. **Runtime self-test.** `GET /audit/egress` returns counters; the frontend
   **Sovereignty panel** shows `external calls blocked: N` live.
5. **OS / package check.** `scripts/verify-airgap.sh` runs from the host and asserts
   there are no established external sockets, complementing the app log. When `/proc`
   or `ss` is unavailable, it supports an explicit `--api-only` fallback in restricted
   environments; that checks the API only.

## What counts as an egress attempt

- A guarded outbound HTTP request to a public host, **even if it fails**.
- A cloud model call.
- Any telemetry, crash reporter, or “phone home” by a dependency.

The guarded request is logged as `egress_blocked` with the destination URL; the socket
check detects established connections not necessarily made by the application. A raw
DNS lookup or non-HTTP connection bypassing the guard does not increment its counters.

## Planned demo script (after integration testing)

1. Open the **Sovereignty** panel: `AIRGAP ON`, `external calls blocked: 0`.
2. Run the end-to-end task (scanned report → approval note `.docx`).
3. Panel still shows `0` external calls; a live log lists only loopback endpoints
   (`127.0.0.1:11434`).
4. Run `scripts/verify-airgap.sh` on an otherwise offline host → prints
   `PASS: no established external socket connections`.
5. Optionally flip `AIRGAP=false` and show the router suddenly list remote models —
   proving the switch is real, then flip it back.

## Known limits (state these honestly)

- The guard protects **this application**. It does not firewall the host; pair it with
  an OS firewall or an isolated deployment network for defence in depth.
- `SANDBOX_BACKEND=auto` uses Docker only when Docker and its pre-pulled image are
  available. `SANDBOX_BACKEND=docker` fails if that isolation is unavailable. The
  subprocess fallback patches ordinary Python socket calls and applies resource
  limits, but it cannot contain hostile native code or subprocess escape attempts.
  Running the API in Compose does not provide a Docker daemon to the agent; use a
  host deployment with Docker access for strong code-execution isolation.
- Packages and model weights are downloaded during setup; afterwards the system can
  run offline. That provisioning traffic is documented in the README so it isn’t
  mistaken for a runtime leak.
- Host-level socket checks include unrelated host processes. A successful API check is
  not proof of zero egress by all processes; run on the air-gapped host with an OS
  firewall or disconnected external interface for that claim.

Application HTTP clients ignore proxy environment variables. Both allowed local and
blocked/external-allowed requests are audited; counters are restored from the durable
audit history on restart. Optional semantic embedding loaders use cached files only
in AIRGAP mode. Unit tests deny network connections even for local hosts; provider
protocol tests use in-memory transports.

## Compose note

The Compose deployment gives Ollama and the backend fixed addresses on a private bridge.
The backend uses Ollama's private IP because the application guard treats an arbitrary
Docker DNS name as external by design. Published service ports bind to `127.0.0.1` by
default. This is useful containment, but the Compose bridge is not a host firewall; the
operator must still disconnect or firewall the host for a real air-gapped deployment.
