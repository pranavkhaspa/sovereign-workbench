# ADR 0001 — Build the agent harness ourselves, with a provider router

- Status: Accepted
- Date: 2026-10-10

## Context

SIH26117 asks for an on-premise agentic workbench that (a) auto-selects across multiple
open-weight models, (b) acts as an agent with local tools, and (c) must run on an 8 GB /
i3 / 2 GB GPU machine. We considered building on a heavy agent framework
(LangChain/LangGraph) versus a small in-repo harness.

## Decision

We implement a **small, original agent loop** (plan → act → observe → reflect) in
`core/agent/`, and a **provider abstraction + registry + router** in `core/llm/`. We may
borrow proven patterns, but we do not depend on a framework for the core control flow.

## Reasons

1. **Footprint.** Frameworks pull large dependency trees; the min-tier machine is 8 GB
   and must stay responsive.
2. **Auditability.** The PS demands provable no-egress and a visible task trajectory; a
   thin, owned loop is easy to instrument and log.
3. **Fit to the wording.** The PS accepts an “original implementation or meaningful
   changes to an existing harness.” An original loop is unambiguously compliant.
4. **Determinism.** We can keep deterministic steps out of the model round-trip, which
   frameworks often make harder (and slower/costlier).

## Consequences

- We own retries, cancellation, and streaming — more code, but fully understood.
- Contributors should not “framework-ify” the core; extend via the **tool registry**.
- If a framework is needed later (e.g. complex multi-agent), wrap it behind the same
  `Tool`/`ModelProvider` interfaces so nothing upstream changes.

## Alternatives considered

- **LangGraph** — good ergonomics, heavier runtime, more magic to audit.
- **Vendor SDK agents** — rejected: hurts the sovereignty/portability story.
