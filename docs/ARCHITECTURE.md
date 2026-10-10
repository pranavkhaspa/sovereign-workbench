# Architecture

This document expands [`CONTEXT.md`](../CONTEXT.md). Read that first.

## 1. System context

```
   ┌──────────────┐        REST + SSE         ┌──────────────────────────────┐
   │  Frontend    │  ───────────────────────▶ │  FastAPI backend             │
   │ React + Vite │  ◀─────────────────────── │  (single process, SQLite)    │
   └──────────────┘   agent step stream       │                              │
                                              │  ┌────────────────────────┐  │
                                              │  │ Agent core             │  │
                                              │  │  planner → executor     │  │
                                              │  │  tools → observer       │  │
                                              │  └───────────┬────────────┘  │
                                              │              │               │
   ┌──────────────┐    OpenAI-compatible      │  ┌───────────▼────────────┐  │
   │ Ollama /     │ ◀───────────────────────  │  │ LLM router + registry  │  │
   │ llama.cpp    │                           │  └───────────┬────────────┘  │
   └──────────────┘                           │              │               │
                                              │  RAG · OCR/Vision · Sandbox  │
                                              │  Deliverables · Audit/Egress │
                                              └──────────────────────────────┘
                                                        │
                                             local files: data/, workspace/,
                                             artifacts/, vectorstore/
```

Everything except the frontend runs as one Python process. The LLM runs as a separate
local process (Ollama/llama.cpp) that the backend talks to over loopback in local
development or a private Docker bridge address in Compose. The backend's air-gap guard
accepts private IPs but treats arbitrary Docker DNS names as external; Compose therefore
connects to Ollama by its private bridge IP. See
[`DEVELOPMENT.md`](DEVELOPMENT.md#compose-deployment) for deployment wiring.

## 2. Layers (dependency direction is downward; nothing lower imports upward)

```
api/            FastAPI routers, request/response only
  ↓
core/agent/     orchestration (plan → act → observe)
  ↓
core/{llm,rag,multimodal,sandbox,deliverables,security}
  ↓
db/, schemas/, config.py, observability/
```

Rules:
- Routers never contain business logic — they validate, call a service, return.
- Feature code never imports a concrete provider; it asks `router.pick(...)`.
- `schemas/` are Pydantic; DB rows are SQLAlchemy models; they are converted at the
  boundary, never passed across layers raw.

## 3. The agent loop (our original harness)

`core/agent/loop.py` implements a bounded **plan → act → observe → reflect** loop:

1. **Plan** — `planner.py` asks the *planning model* for a small ordered plan
   (JSON), given the task, available tools, and retrieved context.
2. **Act** — `executor.py` runs the next step. If it is a tool call, it validates
   arguments against the tool's JSON schema, checks permissions, and invokes it.
3. **Observe** — results are appended to `memory.py` (scratchpad + artifacts +
   citations) and emitted as SSE events.
4. **Reflect** — if a step failed, the planner may re-plan (bounded retries). The loop
   stops on completion, a hard step cap, or user cancel.

Why a custom loop instead of a framework: it must run on an 8 GB box, stay auditable,
and satisfy the PS wording (“original implementation / meaningful changes to an
existing harness”). The design borrows proven ReAct patterns but keeps the bus thin —
deterministic steps do not round-trip through the model unless they must.

Tools (`core/agent/tools/`) implement one ABC:

```python
class Tool(ABC):
    name: str
    description: str
    args_schema: type[BaseModel]          # -> JSON schema for the model
    requires_network: bool = False
    async def run(self, args: BaseModel, ctx: ToolContext) -> ToolResult: ...
```

Registry discovers tools, exposes their schemas to the planner, and dispatches calls.
Adding a tool = add a class + register it. No core changes.

## 4. LLM layer (provider + registry + router)

- `providers/openai_compatible.py` — one adapter for **Ollama `/v1`, vLLM, OpenAI,
  OpenRouter**. `providers/llamacpp.py` — llama.cpp server. Both implement
  `ModelProvider` (`chat()`, `stream()`, `embed()` optional).
- `registry.py` loads `models/models.toml`: each entry has `id`, `provider`,
  `capabilities` (`chat|code|vision|embed|plan`), `tier` (`min|standard|large|remote`),
  `context`, and `notes`.
- `router.py` classifies the task (heuristics + a tiny model when available) into a
  capability need, then selects the best **available** model for the configured
  hardware tier. Remote providers are filtered out when `AIRGAP=true`.

This is the mechanism that satisfies “model auto-selection across ≥2 task types” and
“add new models without redesign” — a registry row + a router rule.

## 5. RAG (grounding)

`ingest` (pdf/txt/md/docx/img via `multimodal/ocr`) → `chunker` (token-aware, keeps
source spans) → `embeddings` (bge-small, CPU, lazy) → `store` (embedded vector DB
behind an interface; default Chroma persistent) → `retriever` (top-k, optional
rerank). Every returned chunk carries a `Citation` (document id, filename, page/span,
score) so answers can be verified.

## 6. Multimodal

- `ocr.py` — Tesseract by default (`pytesseract`), PaddleOCR optional; turns scanned
  pages/drawings into text with bounding boxes where available.
- `vision.py` — sends an image + question to the router-selected vision model
  (Moondream2 / SmolVLM on min tier; Qwen2-VL on large) for description and Q&A.

## 7. Sandbox

`Sandbox.run(code, lang) -> ExecResult`. Two implementations:
- `docker_sandbox.py` (preferred): `--network none`, `--memory`, `--cpus`, `--pids-limit`,
  `--read-only` rootfs + tmpfs `/tmp`, workspace bind-mounted read-write, hard timeout.
- `subprocess_sandbox.py` (fallback): `resource` rlimits (CPU, address space, file
  size, no core), restricted env, `cwd` jailed to the workspace. Best-effort; document
  clearly that Docker is required for strong isolation.

The sandbox is chosen at startup: Docker if available, else subprocess.

## 8. Deliverables

`docx_writer`, `pptx_writer`, `xlsx_writer` produce files into `data/artifacts/` and
register an `Artifact` row. Calculations are rendered with steps. Code results include
stdout/stderr and a verification note.

## 9. Security: egress guard + audit

- `security/airgap.py` — `EgressGuard` wraps every outbound HTTP client. In air-gap
  mode it allows only loopback/private addresses and **blocks + records** everything
  else. It is the single choke point; no feature creates its own raw client.
- `security/audit.py` — append-only events in SQLite: `egress_blocked`,
  `egress_allowed_local`, `tool_call`, `model_selected`, `artifact_created`,
  `task_started/ended`. The `/audit/egress` endpoint powers the sovereignty panel.

See [`SOVEREIGNTY.md`](SOVEREIGNTY.md) for how we prove the claim.

## 10. Persistence

SQLite (single file, zero-ops) via SQLAlchemy 2.0, sync engine, plus a local vector
store directory. Tables: `tasks`, `steps`, `documents`, `chunks`, `artifacts`,
`audit_events`. Easy to migrate to Postgres later by swapping `DATABASE_URL`.

## 11. Configuration & hardware tiers

`config.py` (pydantic-settings) exposes `HARDWARE_TIER` (`min|standard|large`) and
`AIRGAP`. The tier constrains which registry models the router will pick, so the same
code runs on the i3/8 GB laptop and on the MRPL GPU server with only env changes.

## 12. Failure handling

- Model unreachable → router falls to next available model of same capability; if none,
  the task returns a clear error (no silent success).
- Tool failure → recorded, fed back to the planner for one re-plan.
- Egress attempt in air-gap → blocked + audited; task continues if it can.
- Sandbox timeout/kill → `ExecResult(timed_out=True)`, surfaced to the user.

## 13. Testing strategy

- Unit: router selection, chunker spans, air-gap allow/deny, sandbox denies network,
  deliverable writers produce valid files.
- Integration: create task → fake provider → tool calls → artifact row; SSE event order.
- CI runs with `AIRGAP=true` and **no network**; any accidental egress fails the build.
