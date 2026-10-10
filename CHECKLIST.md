# CHECKLIST.md — Build Plan

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked

Owners: **Rohit = frontend** (+ any UI copy, screenshots, demo assets).
**Backend/infra = the other teammate.** Work in parallel against the API contract in
§4. Do not wait for each other.

---

## 0. How to work (both people, every task)

1. `git checkout -b <type>/<scope>-<short>` off `main` (e.g. `feat/frontend-chat-stream`).
2. Make small commits with Conventional Commit messages.
3. Run the local checks for your area (`make lint`, `make test`).
4. Push, open a PR using the template, request the teammate as reviewer.
5. One approval + green CI required before merge. Squash merge.

**Rohit:** every frontend item below lists *file(s)*, *what*, *API used*, and *done
when*. Mock support is planned under §7.1; `frontend/src/api/mock.ts` and a
`VITE_USE_MOCK` switch are not yet present in the current frontend.

---

## 1. Repo & foundation (backend/infra)

- [x] Create repo skeleton, `CONTEXT.md`, `CHECKLIST.md`, `README.md`, `LICENSE` (Apache-2.0)
- [x] `docs/ARCHITECTURE.md`, `docs/SOVEREIGNTY.md`, `docs/MODELS.md`, `docs/adr/0001`
- [~] `.github/workflows/*` CI (backend, frontend, docker, codeql, licences; lint/licence failures pending)
- [x] `scripts/bootstrap.sh` (venv + install backend & frontend deps)
- [~] `scripts/pull-models.sh` (registry selection and dry-run verified; live Ollama pull pending)
- [x] `scripts/dev.sh` (run backend + frontend together)
- [x] `scripts/verify-airgap.sh` (assert no external sockets)
- [ ] `models/models.toml` registry filled for min tier + large tier + remote
- [~] `docker-compose.yml` (+ `.gpu.yml` profile; parsed but Docker config/build pending)
- [x] `make` targets: `dev`, `lint`, `test`, `build`, `verify-airgap`

Setup notes: the repository now includes Git metadata after the baseline commit and a
committed frontend lockfile; bootstrap and CI use `npm ci`. There is still no frontend
`test` script, so `make test` reports the gap instead of invoking an undeclared command.
The implemented route and SSE details are documented in
[`docs/FRONTEND_HANDOFF.md`](docs/FRONTEND_HANDOFF.md); the current UI's live stream is
`POST /api/chat`.

Verification blockers outside this setup scope: backend Ruff/Black checks fail on backend
sources (mypy passes), and the Python
dependency licence allow-list currently rejects MPL-2.0 packages
(`certifi`, `pathspec`). The minimum-tier Qwen2.5 3B and Coder 3B weights in the registry
also carry the Qwen Research License rather than a permissive licence; choose compliant
registry models before claiming the all-permissive runtime requirement. A Compose build,
GPU run, and live model pull still need Docker/Ollama on the deployment host.

## 2. Backend — LLM layer (backend/infra)

- [ ] `core/llm/provider.py` — `ChatMessage`, `Completion`, `ModelProvider` ABC
- [ ] `core/llm/providers/openai_compatible.py` — works with Ollama `/v1`, vLLM, OpenAI, OpenRouter
- [ ] `core/llm/providers/llamacpp.py` — llama.cpp server adapter
- [ ] `core/llm/registry.py` — load `models/models.toml`, expose available models by capability
- [ ] `core/llm/router.py` — classify task → pick model by capability + hardware tier + availability
- [ ] `core/llm/router.py` — **must demonstrate selection across ≥2 task types** (code vs summary)
- [ ] `core/llm/registry.py` — remote providers disabled when `AIRGAP=true`
- [ ] Unit tests: router picks code model for code tasks, vision model for images

## 3. Backend — Agent core (backend/infra)

- [ ] `core/agent/loop.py` — plan → act → observe → iterate, bounded steps, streaming events
- [ ] `core/agent/planner.py` — decomposes task into steps; can re-plan on failure
- [ ] `core/agent/executor.py` — runs a step, dispatches to tools
- [ ] `core/agent/memory.py` — scratchpad + retrieved context + artifact refs
- [ ] `core/agent/tools/base.py` — `Tool` ABC + JSON schema + `ToolResult`
- [ ] `core/agent/tools/registry.py` — register/discover tools
- [ ] Tool: `fs_tools.py` — read/write/list inside a jailed workspace dir
- [ ] Tool: `code_exec.py` — run code via sandbox, return stdout/stderr/exit
- [ ] Tool: `spreadsheet.py` — read/compute `.xlsx` (openpyxl)
- [ ] Tool: `doc_search.py` — query the local knowledge base (RAG) with citations
- [ ] Tool: `ocr_vision.py` — OCR + local vision description of an image/scanned page
- [ ] Emit SSE events: `plan`, `step_start`, `tool_call`, `tool_result`, `token`, `artifact`, `done`, `error`

<a id="api-contract"></a>

## 4. API contract (freeze early — Rohit codes against this)

Base URL `/api`. All JSON unless noted. Errors: `{ "error": { "code", "message" } }`.

**Implementation reconciliation needed:** this table is the team's target contract.
The current `GET /api/models` returns `{ "models": ModelInfo[] }` rather than a bare
array, the current artifact download route is `GET /api/artifacts/{id}/download`,
and the current frontend streams through `POST /api/chat`. Some FastAPI errors still
use `detail` rather than the envelope above. Keep the frontend and backend aligned
when freezing this section; the setup verifier uses only `/api/health` and
`/api/audit/egress`.

| Method | Path | Body / params | Returns | Used by |
| --- | --- | --- | --- | --- |
| GET | `/health` | – | `{status, version, airgap, models_ready}` | shell |
| GET | `/models` | – | `ModelInfo[]` `{id,label,capabilities[],tier,provider,available,size_hint}` | Models panel |
| GET | `/models/{id}` | – | `ModelInfo` | Models panel |
| POST | `/tasks` | `{prompt, attachments[], model_id?, options}` | `Task` | composer |
| GET | `/tasks` | `?limit&cursor` | `Task[]` | history |
| GET | `/tasks/{id}` | – | `Task` (with steps) | task view |
| GET | `/tasks/{id}/events` | SSE | event stream (see §3) | live timeline |
| POST | `/tasks/{id}/cancel` | – | `{ok}` | task view |
| POST | `/documents` | multipart file(s) | `{document_id, chunks, status}` | upload |
| GET | `/documents` | – | `Document[]` | knowledge base |
| GET | `/documents/{id}` | – | `Document` | knowledge base |
| DELETE | `/documents/{id}` | – | `{ok}` | knowledge base |
| POST | `/documents/search` | `{query, top_k}` | `Chunk[]` with `citation` | search |
| GET | `/artifacts` | – | `Artifact[]` | artifacts |
| GET | `/artifacts/{id}` | – | file bytes (`Content-Disposition`) | download |
| GET | `/audit` | `?limit&type` | `AuditEvent[]` | audit panel |
| GET | `/audit/egress` | – | `{blocked, allowed_local, external_allowed, airgap}` | sovereignty panel |

Types live in `frontend/src/api/types.ts` and mirror `backend/src/sovereign_workbench/schemas/`.

## 5. Backend — RAG, multimodal, deliverables, sandbox, security

- [ ] `core/rag/ingest.py` — accept pdf/txt/md/docx/img, extract text
- [ ] `core/rag/chunker.py` — token-aware chunking with source spans (for citations)
- [ ] `core/rag/embeddings.py` — bge-small via sentence-transformers (lazy import)
- [ ] `core/rag/store.py` — embedded vector store (chromadb persistent) behind an interface
- [ ] `core/rag/retriever.py` — top-k + optional rerank, returns `Citation`
- [ ] `core/multimodal/ocr.py` — Tesseract default, PaddleOCR optional
- [ ] `core/multimodal/vision.py` — call vision model via router
- [ ] `core/deliverables/docx_writer.py` (python-docx)
- [ ] `core/deliverables/pptx_writer.py` (python-pptx)
- [ ] `core/deliverables/xlsx_writer.py` (openpyxl)
- [ ] `core/sandbox/base.py` — `Sandbox` ABC (`run(code, lang) -> ExecResult`)
- [ ] `core/sandbox/docker_sandbox.py` — `--network none`, memory/cpu limits, tmpfs
- [ ] `core/sandbox/subprocess_sandbox.py` — rlimits fallback (documented as best-effort)
- [ ] `core/security/airgap.py` — `EgressGuard`; blocks+logs non-local hosts in air-gap
- [ ] `core/security/audit.py` — append-only audit events (SQLite)

## 6. Backend — persistence, app, config, tests

- [ ] `db/models.py` — `Task`, `Step`, `Document`, `Artifact`, `AuditEvent` (SQLAlchemy)
- [ ] `db/session.py` — SQLite engine + session factory
- [ ] `schemas/*.py` — Pydantic models matching §4
- [ ] `config.py` — `pydantic-settings`; `AIRGAP`, `OLLAMA_BASE_URL`, provider keys, paths
- [ ] `main.py` — FastAPI app, CORS, routers, lifespan (DB init, load registry)
- [ ] `api/routes/*.py` — implement every row of §4
- [ ] `api/deps.py` — DI for db, registry, router, agent
- [ ] Tests: unit (router, chunker, airgap, sandbox-denies-network) + integration (create task → mock model → artifact)
- [ ] Coverage ≥ 70% on `core/`

## 7. FRONTEND — owner: Rohit

> Stack: **React 18 + Vite + TypeScript (strict) + Tailwind CSS + TanStack Query + Zustand.**
> Design language: dense, calm,
> "industrial console" — dark by default, one accent colour, monospace for logs.
> Everything must be keyboard-accessible and work at 1280×720.
>
> **State: delivered on `feat/frontend-rohit-batch`.** The baseline `src/pages/` +
> `src/components/` structure was kept instead of the planned `features/` tree — no
> behaviour depends on the path, and mixing a structural rename with behaviour changes
> would have been unreviewable. Names below are the files that exist; the planned name
> appears in parentheses where it differs.

### 7.1 Foundation

- [x] `src/api/client.ts` — typed fetch wrapper, base `/api`, error normalization (the `VITE_USE_MOCK` switch lives in `src/api/transport.ts`)
- [x] `src/api/transport.ts` — one function per row of §4 behind a `Transport` seam: `fetchTransport` or `mockTransport`
- [x] `src/api/mock.ts` — mock all endpoints incl. a **fake SSE stream** that emits the §3 events on a timer (`frontend/scripts/seed.ts` supplies tasks/artifacts/documents/audit)
- [x] `src/api/types.ts` — mirror §4 types exactly (single source for the team)
- [x] `src/api/sse.ts` (`src/lib/sse.ts`) — frame parsing + typed event reader; reconnect resumes `/tasks/{id}/events`
- [x] `src/lib/format.ts` — bytes, durations, timestamps (IST-friendly `en-IN`)
- [x] `src/store/useSession.ts` (`session.ts`) — active task, selected model, attachments, airgap flag; run state in `src/store/useWorkbench.ts`
- [x] App shell: `src/App.tsx` — left rail nav + main + right panel (pages under `src/pages/`)
- [x] `src/components/ui/*` — Button, Input, Textarea, Select, Badge, Card, Tabs, Dialog, Toast, Spinner, Tooltip, EmptyState, CopyButton (headless/simple, no heavy UI kit)

### 7.2 Chat / Composer (core flow)

- [x] `src/pages/Workbench.tsx` (`ChatView.tsx`) — message list (user/assistant/system), auto-scroll, streaming text
- [x] `src/components/Composer.tsx` — textarea (auto-grow), send (⌘/Ctrl+Enter), stop button while streaming, attachment button
- [x] dropzone in `Composer.tsx` (`AttachmentTray.tsx`) — drag-drop + file picker (pdf, png, jpg, xlsx, docx, txt, md), file badges, remove
- [x] `src/components/AnswerMarkdown.tsx` + `CitationChips.tsx` (`MessageBubble.tsx`) — markdown render (react-markdown + rehype-highlight) with **citation chips** that open the source snippet
- [x] model picker in `Composer.tsx` (`ModelPicker.tsx`) — reads `GET /models`, groups by capability, marks `available:false` disabled, shows airgap badge
- [x] Wire composer → `POST /chat` (SSE) → subscribe `/tasks/{id}/events` on reconnect; stop → `POST /tasks/{id}/cancel`
- [x] **Done when:** with mock on, sending a prompt streams a plausible agent run end-to-end; with backend on, it renders the real stream.

### 7.3 Agent timeline

- [x] `src/components/AgentTimeline.tsx` (`TimelinePanel.tsx`) — vertical list of steps from SSE
- [x] icon per event type (`StepItem`), expandable tool call (args + result), per-row `+elapsed` timing
- [x] pretty-printed tool JSON, collapsible, copy button on the expanded block (`ToolCallCard`)
- [x] live status derived from events (`live execution` / `run complete` / `stopped by operator` / `stream error`)
- [x] **Done when:** each §3 event type has a distinct, legible rendering and errors are red and readable. — covered by `src/components/AgentTimeline.test.tsx`

### 7.4 Artifacts

- [x] `src/components/ArtifactList.tsx` (`ArtifactsPanel.tsx`) — list from `GET /artifacts`, filter by task
- [x] artifact card (`ArtifactCard`) — type icon (docx/pptx/xlsx/code/log), size, created-at, Download link with the correct filename
- [x] `src/components/CodeViewer.tsx` — read-only code preview (for code artifacts), copy button
- [x] `src/components/DocPreview.tsx` — for `.docx`/`.xlsx` a text/table extract via `transport.readArtifact`, else "download to view"
- [x] **Done when:** a produced artifact appears without refresh (query invalidated when the run ends) and downloads with the correct filename/content-type.

### 7.5 Knowledge base (documents / RAG)

- [x] `src/pages/Documents.tsx` (`DocumentsView.tsx`) — table: name, type, chunks, status, uploaded-at; delete action with confirmation
- [x] upload zone (Composer dropzone + Documents page) — multi-file upload with status and chunk count after ingest
- [x] search panel in `Documents.tsx` (`SearchPanel.tsx`) — query box → `POST /documents/search` (GET fallback) → ranked chunks with **citations** (file + page/span + score)
- [x] **Done when:** uploading a PDF shows chunk count, and search returns cited excerpts.

### 7.6 Sovereignty / Audit

- [x] `src/components/SovereigntyPanel.tsx` + `src/pages/Sovereignty.tsx` — big status: `AIRGAP ON`, **external calls blocked: N**, allowed local endpoints list, refresh
- [x] audit table in `src/pages/Sovereignty.tsx` — filterable `GET /audit` (type, time, actor, detail), monospace
- [ ] Optional: sparkline of egress attempts over time (hide if zero) — deferred
- [x] **Done when:** the panel visibly proves "no external calls" — this is a judged requirement; screenshot `docs/assets/03-sovereignty.png` (shot list in `docs/DEMO.md`).

### 7.7 Models & Settings

- [x] `src/pages/Models.tsx` — cards from `GET /models`: id, capabilities, tier, provider, availability, active-select
- [x] `src/pages/Settings.tsx` (`SettingsView.tsx`) — read-only env/config summary (base URL, airgap, hardware tier), theme toggle (dark/light), "copy diagnostics" button
- [x] **Done when:** model routing is visible and the active model is selectable.

### 7.8 Polish, a11y, tests

- [x] Responsive layout (nav collapses < 900 px, breakpoints at 1120/900/620); 1280×720 not yet visually audited
- [x] Keyboard shortcuts: focus composer (`/`), send (⌘/Ctrl+Enter), stop (Esc + Stop button), toggle timeline (⌘/Ctrl+Shift+T), sovereignty panel (⌘/Ctrl+Shift+S)
- [x] Loading / empty / error states for every panel
- [x] `vitest` tests: `client.ts`, `sse.ts`, model grouping, `AgentTimeline`, `ArtifactList` — 44 tests, `npm run test`
- [x] `eslint` + `prettier` clean; `npm run build` succeeds; bundle 83.6 KB gzip initial + 102 KB lazy markdown chunk (limit 500 KB)
- [x] README section: "Frontend (Rohit)" with run instructions

### 7.9 Demo assets (Rohit)

- [x] Seed script `frontend/scripts/seed.ts` to populate mock tasks/artifacts for screenshots (`VITE_USE_MOCK=true`)
- [~] 3 screenshots for the SIH idea PPT + README (`docs/assets/`) — shot list written in `docs/DEMO.md`; images still to be captured by Rohit
- [x] 2-minute demo script timing (Problem 15s / live run 60s / how built 30s / next 15s) — `docs/DEMO.md`

## 8. CI & quality (backend/infra)

- [~] `backend-ci.yml` — ruff, black --check, mypy, pytest (pytest/mypy pass; Ruff/Black need backend fixes)
- [~] `frontend-ci.yml` — eslint, tsc --noEmit, vitest, build (all local checks pass; CI run pending)
- [~] `docker.yml` — build backend + frontend images; compose smoke test (awaiting Docker run)
- [~] `codeql.yml` — code scanning (python + javascript; awaiting CI run)
- [!] `license-check.yml` — dependency licence allow-list (current Python dependency graph contains MPL-2.0)
- [ ] Branch protection rules documented in `CONTRIBUTING.md`

## 9. Demo-readiness (both)

- [ ] End-to-end: scanned report → findings → `.docx` approval note
- [ ] Coding task runs in sandbox, verified
- [ ] Multimodal task on a drawing/photo
- [ ] Router visibly switches models between at least two task types
- [ ] Sovereignty panel shows 0 external calls (run `scripts/verify-airgap.sh`)
- [ ] Runs on 8 GB / i3 / 2 GB GPU with minimum-tier models (`scripts/pull-models.sh`)
- [ ] README + short demo video

## 10. Stretch (only if time)

- [ ] Reranker for RAG (bge-reranker-base)
- [ ] Fine-grained tool permissions per workspace
- [ ] Local TTS read-back of answers (ElevenLabs optional; Piper/Coqui local default)
- [ ] Multi-user auth (local accounts) + per-user workspaces
- [ ] Export full task trajectory as Markdown/PDF
