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
- [~] `.github/workflows/*` CI (local lint/tests/licences verified; remote runs require GitHub authentication)
- [x] `scripts/bootstrap.sh` (venv + install backend & frontend deps)
- [~] `scripts/pull-models.sh` (registry selection and dry-run verified; live Ollama pull pending)
- [x] `scripts/dev.sh` (run backend + frontend together)
- [x] `scripts/verify-airgap.sh` (assert no external sockets)
- [x] `models/models.toml` registry filled for min tier + large tier + remote
- [~] CPU/GPU Compose configurations validated; image builds require Docker-capable host
- [x] `make` targets: `dev`, `lint`, `test`, `build`, `verify-airgap`

Setup notes: the repository now includes Git metadata after the baseline commit and a
committed frontend lockfile; bootstrap and CI use `npm ci`. There is still no frontend
`test` script, so `make test` reports the gap instead of invoking an undeclared command.
The implemented route and SSE details are documented in
[`docs/FRONTEND_HANDOFF.md`](docs/FRONTEND_HANDOFF.md); the current UI's live stream is
`POST /api/chat`.

Backend completion status and remaining deployment gates are tracked in
[`docs/BACKEND_STATUS.md`](docs/BACKEND_STATUS.md). The licence workflow checks
documented certifi/pathspec exceptions separately; minimum-tier weights are now
Apache-2.0 1.5B models. Docker build/sandbox and live model/hardware checks require
the deployment host. See ADR 0002 for reconciled runtime decisions.

## 2. Backend — LLM layer (backend/infra)

- [x] `core/llm/provider.py` — `ChatMessage`, `Completion`, `ModelProvider` ABC
- [x] `core/llm/providers/openai_compatible.py` — OpenAI-compatible protocol, tested in-memory
- [x] `core/llm/providers/llamacpp.py` — llama.cpp server adapter
- [x] `core/llm/registry.py` — load registry and probe installed models (including `:latest` aliases)
- [x] `core/llm/router.py` — classify task → model by capability, hardware tier and availability
- [x] Model selection across ≥2 task types (code vs summary), covered by tests
- [x] Remote providers disabled when `AIRGAP=true`
- [x] Unit tests for code/general/vision model selection

## 3. Backend — Agent core (backend/infra)

- [x] `core/agent/loop.py` — bounded plan/act/observe, provider-token streaming
- [x] `core/agent/planner.py` — schema-informed plans and bounded failure recovery
- [x] `core/agent/executor.py` — validation, permissions, timeouts, dispatch
- [x] `core/agent/memory.py` — observations, citations, artifact refs
- [x] `core/agent/tools/base.py` — `Tool` ABC + JSON schema + `ToolResult`
- [x] `core/agent/tools/registry.py` — registered/discoverable tools
- [x] Jailed filesystem read/write/list and binary-document extraction tools
- [x] Code execution returns stdout/stderr/exit and source/log artifacts
- [x] Read XLSX with openpyxl; write computed XLSX with XlsxWriter
- [x] Local document search with file/page/span citations
- [x] OCR + router-selected vision description tool
- [x] Durable SSE: `plan`, `step_start`, `tool_call`, `tool_result`, `token`, `artifact`, `done`, `error`

<a id="api-contract"></a>

## 4. API contract (freeze early — Rohit codes against this)

Base URL `/api`. All JSON unless noted. Errors: `{ "error": { "code", "message" } }`.

The table below and [`docs/FRONTEND_HANDOFF.md`](docs/FRONTEND_HANDOFF.md) describe
the implemented contract. `POST /api/chat` is the create-and-stream shortcut;
artifact downloads support both the short path and `/download`.

| Method | Path | Body / params | Returns | Used by |
| --- | --- | --- | --- | --- |
| GET | `/health` | – | `{status, version, airgap, models_ready}` | shell |
| GET | `/models` | – | `{models: ModelInfo[]}` | Models panel |
| GET | `/models/{id}` | – | `ModelInfo` | Models panel |
| POST | `/tasks` | `{prompt, attachments[], model_id?, options}` | `Task` | composer |
| GET | `/tasks` | `?limit&cursor` | `Task[]` | history |
| GET | `/tasks/{id}` | – | `Task` (with steps) | task view |
| GET | `/tasks/{id}/events` | SSE | event stream (see §3) | live timeline |
| POST | `/tasks/{id}/cancel` | – | `{ok}` | task view |
| POST | `/documents` | multipart `file` (one per request) | `{document_id, chunks, status}` | upload |
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

- [x] `core/rag/indexer.py` + `extract.py` — PDF/TXT/MD/DOCX/images/XLSX ingestion
- [x] Character-bounded chunks with page and normalized-text spans (ADR 0002)
- [x] Hashing embeddings and lazy, cache-only-in-airgap sentence-transformers
- [x] SQLite cosine vector store behind retriever facade (ADR 0002)
- [x] Top-k retrieval returning citations; reranking remains stretch scope
- [x] Tesseract OCR and page-at-a-time scanned PDF rendering; PaddleOCR deferred
- [x] Router-selected vision model with local image/PDF payloads
- [x] DOCX writer and approval-note tool
- [x] PPTX writer and presentation tool
- [x] XLSX writer with cached computed values; safe arithmetic tool
- [x] Sandbox ABC
- [~] Docker sandbox implemented; actual container execution requires Docker-capable host
- [x] Subprocess rlimits fallback, bounded output and process cleanup
- [x] Egress guard blocks/audits external hosts and disables proxy-environment bypass
- [x] SQLite audit events and restart-persistent egress counters

## 6. Backend — persistence, app, config, tests

- [x] SQLAlchemy tasks/steps/documents/chunks/artifacts/audit/task-events
- [x] SQLite sessions, foreign keys, WAL and additive task migration
- [x] Pydantic schemas and normalized HTTP/validation errors
- [x] Settings for airgap, providers, paths and sandbox/agent limits
- [x] FastAPI lifecycle, model probing, interrupted-task recovery and worker shutdown
- [x] Every implemented §4 route, pagination, durable event replay and cancellation
- [x] Dependency injection for registry/router/tools/runner
- [x] Offline unit/integration suite including real OCR and downloadable office files
- [x] Core coverage ≥70%, enforced in CI

## 7. FRONTEND — owner: Rohit

> Stack: **React 18 + Vite + TypeScript (strict) + Tailwind CSS + TanStack Query + Zustand.**
> API client + types + mocks are pre-scaffolded. Design language: dense, calm,
> "industrial console" — dark by default, one accent colour, monospace for logs.
> Everything must be keyboard-accessible and work at 1280×720.

### 7.1 Foundation

- [ ] `src/api/client.ts` — typed fetch wrapper, base `/api`, error normalization, `VITE_USE_MOCK` switch
- [ ] `src/api/endpoints.ts` — one function per row of §4
- [ ] `src/api/mock.ts` — mock all endpoints incl. a **fake SSE stream** that emits the §3 events on a timer
- [ ] `src/types/api.ts` — mirror §4 types exactly (single source for the team)
- [ ] `src/lib/sse.ts` — `EventSource` wrapper with reconnect + typed event parsing
- [ ] `src/lib/format.ts` — bytes, durations, timestamps (IST-friendly)
- [ ] `src/store/session.ts` (Zustand) — active task, selected model, attachments, airgap flag
- [ ] App shell: `App.tsx` + `components/AppShell.tsx` — left rail nav + main + right panel
- [ ] `components/ui/*` — Button, Input, Textarea, Select, Badge, Card, Tabs, Dialog, Toast, Spinner, Tooltip, EmptyState (headless/simple, no heavy UI kit)

### 7.2 Chat / Composer (core flow)

- [ ] `features/chat/ChatView.tsx` — message list (user/assistant/system), auto-scroll, streaming text
- [ ] `features/chat/Composer.tsx` — textarea (auto-grow), send (⌘/Ctrl+Enter), stop button while streaming, attachment button
- [ ] `features/chat/AttachmentTray.tsx` — drag-drop + file picker (pdf, png, jpg, xlsx, docx, txt, md), thumbnails, remove
- [ ] `features/chat/MessageBubble.tsx` — markdown render (react-markdown + rehype-highlight) with **citation chips** that open the source snippet
- [ ] `features/chat/ModelPicker.tsx` — reads `GET /models`, groups by capability, marks `available:false` disabled, shows airgap badge
- [ ] Wire composer → `POST /tasks` → subscribe to `/tasks/{id}/events`
- [ ] **Done when:** with mock on, sending a prompt streams a plausible agent run end-to-end; with backend on, it renders the real stream.

### 7.3 Agent timeline

- [ ] `features/timeline/TimelinePanel.tsx` — vertical list of steps from SSE
- [ ] `features/timeline/StepItem.tsx` — icon per event type, expandable tool call (args + result), timing
- [ ] `features/timeline/ToolCallCard.tsx` — pretty-print tool JSON, collapsible, copy button
- [ ] Show a live "thinking / calling tool / writing file" status derived from events
- [ ] **Done when:** each §3 event type has a distinct, legible rendering and errors are red and readable.

### 7.4 Artifacts

- [ ] `features/artifacts/ArtifactsPanel.tsx` — list from `GET /artifacts`, filter by task
- [ ] `features/artifacts/ArtifactCard.tsx` — type icon (docx/pptx/xlsx/code/log), size, created-at, Download button
- [ ] `features/artifacts/CodeViewer.tsx` — read-only code preview (for code artifacts), copy button
- [ ] `features/artifacts/DocPreview.tsx` — for `.docx`/`.xlsx` show a text/table extract if API provides it, else "download to view"
- [ ] **Done when:** a produced artifact appears without refresh and downloads with the correct filename/content-type.

### 7.5 Knowledge base (documents / RAG)

- [ ] `features/documents/DocumentsView.tsx` — table: name, type, chunks, status, uploaded-at; delete action
- [ ] `features/documents/UploadZone.tsx` — multi-file upload with progress
- [ ] `features/documents/SearchPanel.tsx` — query box → `POST /documents/search` → ranked chunks with **citations** (file + page/span)
- [ ] **Done when:** uploading a PDF shows chunk count, and search returns cited excerpts.

### 7.6 Sovereignty / Audit

- [ ] `features/sovereignty/SovereigntyPanel.tsx` — big status: `AIRGAP ON`, **external calls blocked: N**, allowed local endpoints list, refresh
- [ ] `features/audit/AuditView.tsx` — filterable table of `GET /audit` (type, time, actor, detail), monospace
- [ ] Optional: sparkline of egress attempts over time (hide if zero)
- [ ] **Done when:** the panel visibly proves "no external calls" — this is a judged requirement; make it screenshot-worthy.

### 7.7 Models & Settings

- [ ] `features/models/ModelsView.tsx` — cards from `GET /models`: id, capabilities, tier, provider, availability, active-select
- [ ] `features/settings/SettingsView.tsx` — read-only env/config summary (base URL, airgap, workspace path), theme toggle, "copy diagnostic" button
- [ ] **Done when:** model routing is visible and the active model is selectable.

### 7.8 Polish, a11y, tests

- [ ] Responsive layout (nav collapses < 900px), no horizontal scroll at 1280×720
- [ ] Keyboard shortcuts: focus composer, send, stop, toggle timeline
- [ ] Loading / empty / error states for every panel
- [ ] `vitest` tests: `client.ts`, `sse.ts`, `ModelPicker`, `TimelinePanel`, `ArtifactsPanel`
- [ ] `eslint` + `prettier` clean; `npm run build` succeeds; bundle < 500 KB gzip (lazy-load heavy views)
- [x] README section: "Frontend (Rohit)" with run instructions

### 7.9 Demo assets (Rohit)

- [ ] Seed script `frontend/scripts/seed.ts` to populate mock tasks/artifacts for screenshots
- [ ] 3 screenshots for the SIH idea PPT + README (`docs/assets/`)
- [ ] 2-minute demo script timing (Problem 15s / live run 60s / how built 30s / next 15s)

## 8. CI & quality (backend/infra)

- [~] `backend-ci.yml` — local checks fixed; remote run pending authenticated GitHub access
- [~] `frontend-ci.yml` — eslint, tsc --noEmit, build (all local checks pass; CI run pending; no test script yet)
- [~] `docker.yml` — build backend + frontend images; compose smoke test (awaiting Docker run)
- [~] `codeql.yml` — code scanning (python + javascript; awaiting CI run)
- [x] `license-check.yml` — permissive allow-list plus named, separately checked MPL exceptions
- [x] Branch protection rules documented in `CONTRIBUTING.md` (admin must enable them)

## 9. Demo-readiness (both)

- [x] Automated real scanned PDF → findings → downloadable `.docx` approval note
- [x] Coding task runs in subprocess sandbox with downloadable verification log
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
