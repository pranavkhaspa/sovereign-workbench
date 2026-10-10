# Security Policy

## Reporting a vulnerability

**Do not open a public issue.** Report privately to the maintainers (e.g. via GitHub
Security Advisories “Report a vulnerability”, or the contact listed on the repo).
Include:

- a description and impact,
- steps to reproduce,
- affected version/commit,
- any suggested fix.

We aim to acknowledge within 72 hours.

## Threat model (what this project takes seriously)

Because this is an **air-gapped** tool for confidential data, the following are
security-relevant and treated as bugs:

1. **Egress leaks** — any code path that can reach a non-loopback/private host while
   `AIRGAP=true`, *even if the request fails*. Blocked attempts must be logged.
2. **Sandbox escapes** — executed code must not reach the network or escape its
   workspace, and must respect memory/CPU/time limits.
3. **Secret exposure** — keys must never be logged, returned by the API, or committed.
4. **Prompt-injection to tool access** — untrusted document content must not be able to
   silently grant itself filesystem or network capabilities.

## Handling secrets

- All secrets live in `.env` (git-ignored). `.env.example` documents the keys only.
- CI never receives real provider keys. Tests run with `AIRGAP=true` and no keys.
- If a secret is committed: rotate it first, then purge history, then open a PR noting
  the rotation.

## Supported versions

Pre-1.0: only the latest `main` is supported.
