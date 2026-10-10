# Frontend handoff

This document is the working contract for the frontend owner. The current UI is
already implemented under `frontend/src`; this guide describes what is available
in the baseline commit and what still needs frontend work.

## 1. Start here

From a fresh checkout:

```bash
./scripts/bootstrap.sh
```

Bootstrap creates `.venv`, installs the backend package with the `dev,ocr` extras,
and runs `npm ci` in `frontend/`. It also copies `.env.example` to `.env` if no
local environment exists. Model weights are not installed by bootstrap.

Run the services in separate terminals:

```bash
# terminal 1, repository root
make backend

# terminal 2, repository root
make frontend
```

The backend is available at `http://127.0.0.1:8000`; Vite serves the UI at
`http://127.0.0.1:5173` and proxies `/api/*` to the backend. `make dev` starts both
services together. `VITE_API_BASE` is empty by default because the browser uses the
Vite proxy in development and the same-origin Nginx proxy in Compose.

The UI can load without Ollama. A task needs an available local model, so install
Ollama and pull the configured models before testing a real agent run:

```bash
./scripts/pull-models.sh --dry-run
./scripts/pull-models.sh
```

## 2. Frontend checks

Run these from `frontend/`:

```bash
npm run lint
npm run typecheck
npm run build
```

The baseline does not declare a frontend test script yet. Add a test runner and
update `package.json`, `package-lock.json`, `Makefile`, and
`.github/workflows/frontend-ci.yml` together when adding tests.

The frontend rules are TypeScript strict, no `any`, functional React components,
TanStack Query for server state, Zustand for UI/session state, and ESLint/Prettier.
Keep the production JavaScript bundle below 500 KB gzip.

## 3. Current frontend structure

The baseline uses a small page/component structure rather than the future feature
directory layout in `CHECKLIST.md`:

| Area | Files |
| --- | --- |
| App shell/navigation | `src/App.tsx`, `src/index.css` |
| Workbench/composer | `src/pages/Workbench.tsx`, `src/components/Composer.tsx` |
| Agent timeline | `src/components/AgentTimeline.tsx`, `src/store/useWorkbench.ts` |
| Artifacts | `src/components/ArtifactList.tsx` |
| Documents/RAG | `src/pages/Documents.tsx` |
| Models | `src/pages/Models.tsx` |
| Sovereignty/audit | `src/pages/Sovereignty.tsx`, `src/components/SovereigntyPanel.tsx` |
| API types/client | `src/api/types.ts`, `src/api/client.ts` |
| SSE parser | `src/api/sse.ts` |
| Session state | `src/store/useSession.ts` |

Keep API calls in `src/api/` and use the shared types. Do not import backend Python
modules into the frontend or duplicate API URLs in page components.

## 4. Implemented API contract

The backend is mounted under `/api`. Responses use ISO-8601 timestamps and UUID
strings in JSON. Errors are normalized by the backend to:

```json
{
  "error": {
    "code": "http_422",
    "message": "...",
    "details": []
  }
}
```

Some FastAPI validation details may be absent from `details`; the shared client
already handles both the normalized `error` shape and legacy `detail` responses.

### Health and sovereignty

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/health` | `{status, version, airgap, hardware_tier, models, models_ready}` |
| GET | `/api/health/egress` | `{airgap, blocked, allowed_local, external_allowed, local_endpoints[]}` |
| GET | `/api/audit/egress` | Same egress response; compatibility alias |
| GET | `/api/audit?limit=200&type=...` | `AuditEvent[]` |

### Models

`GET /api/models` returns an envelope, not a bare array:

```json
{
  "models": [
    {
      "id": "planner-min",
      "label": "...",
      "provider": "ollama",
      "remote": false,
      "tier": "min",
      "capabilities": ["plan", "chat"],
      "available": true,
      "size_hint": null,
      "notes": "..."
    }
  ]
}
```

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/models` | List registry models and current availability |
| GET | `/api/models/{id}` | Read one model |
| POST | `/api/models/refresh` | Probe local provider availability and return the same envelope |

Remote models are rejected when `AIRGAP=true`; unavailable models must not be
presented as selectable for a run.

### Tasks and agent events

The current Workbench uses `POST /api/chat` because it creates a task and returns
the live SSE response in one request. The request body is:

```json
{
  "prompt": "Draft an approval note",
  "attachments": ["document-uuid"],
  "model_id": null,
  "options": {
    "allow_network": false,
    "write_files": true,
    "run_code": false,
    "max_steps": 8
  }
}
```

`attachments` contains document IDs from `/api/documents`, not local file
paths. The upload must complete before the document can be attached.

The response is `text/event-stream`. Each frame is separated by a blank line and
has this form:

```text
event: token
data: {"type":"token","task_id":"...","at":"...","data":{"text":"..."}}

```

Persisted frames additionally include `id: <integer>` before `event:` and an `id`
field in the JSON envelope. Treat it as an opaque resume cursor. Events emitted are:

| Event | Important `data` fields |
| --- | --- |
| `task_created` | `task_id`, `status`; emitted by the HTTP route before agent events |
| `plan` | `steps[]`, `model_id`, `planning_model_id`, `capability` |
| `step_start` | `index`, `title` |
| `tool_call` | `tool`, `args` |
| `tool_result` | `tool`, `ok`, `output`, `error`, structured `data` (citations/calculations/etc.) |
| `token` | `text` |
| `artifact` | artifact fields including `id`, `filename`, `kind`, `size_bytes` |
| `done` | `artifacts[]`, `citations[]` |
| `error` | `code`, `message`, optional `tool` |

The existing `src/api/sse.ts` uses `fetch`, not `EventSource`, because the stream
starts with a JSON POST body. Preserve the parser's support for named events and
the nested `data` object.

There is also a two-request task flow for reconnect/history work:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/tasks` | Create and persist a task; returns a full `Task` with HTTP 201 |
| GET | `/api/tasks?limit=50&cursor=<last-task-id>` | Recent task history, descending order |
| GET | `/api/tasks/{id}` | Full task, persisted steps, and artifacts |
| GET | `/api/tasks/{id}/events?after=<event-id>` | SSE replay/continuation; also accepts `Last-Event-ID` |
| POST | `/api/tasks/{id}/cancel` | Cancel a queued/running task; returns `{ok: true}` |

The current UI uses `GET /api/tasks/{id}` for recovery. A stop button currently
stops the browser stream; wiring it to the cancel route is a high-priority follow-up
before calling cancellation complete.

Execution begins on the first SSE subscription and continues after a disconnect.
Multiple subscribers do not execute the task twice. All tokens and events survive
a backend restart. Previously running work becomes `error/TASK_INTERRUPTED` after
a crash; the user may submit a new task. Runs are serialized on the minimum tier.
Final answers stream actual provider tokens. The agent may emit additional `plan`
events for recovery; never assume a single plan event per run.

Artifact tools can always produce the requested downloadable deliverable. `write_files`
controls the general `write_file` tool; `run_code` controls sandbox execution. Code runs
produce a source artifact and a separate `.log` with stdout, stderr, exit and timeout.

### Documents and search

| Method | Path | Body/response |
| --- | --- | --- |
| POST | `/api/documents` | Multipart field `file`; returns `{document_id, chunks, status}` |
| GET | `/api/documents` | `Document[]` |
| GET | `/api/documents/{id}` | One `Document` |
| DELETE | `/api/documents/{id}` | `{ok: true}` |
| POST | `/api/documents/search` | JSON `{query, top_k}` → `Chunk[]` |
| GET | `/api/documents/search?q=...&top_k=...` | Compatibility search route → `Chunk[]` |

Allowed upload suffixes are PDF, PNG/JPG/TIFF/BMP/WEBP, DOCX, TXT/MD, CSV, XLSX,
and XLSM. The backend currently enforces a 50 MB per-file limit and indexes one
multipart file per request. `Chunk.citation` includes `document_id`, `filename`,
optional `page`/`span`, and `score`.

### Artifacts

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/artifacts` | `Artifact[]`, optional `?task_id=...` |
| GET | `/api/artifacts/{id}/download` | File bytes with `Content-Disposition` filename |
| GET | `/api/artifacts/{id}` | Compatibility alias for the download route |

The current artifact list refreshes after a run. Use
`artifactDownloadUrl(id)` from `src/api/client.ts` so the path stays centralized.

## 5. Current gaps for the frontend owner

These are known follow-ups for the next frontend branch:

1. Wire the stop control to `POST /api/tasks/{id}/cancel`, then abort the browser
   stream after the backend acknowledges cancellation.
2. Make reconnect resume `/api/tasks/{id}/events` or clearly distinguish polling
    recovery from live SSE resume. Reconstruct text from persisted `token` events,
    and resume after the last processed event ID to avoid duplicate text.
3. Add document delete UI and an artifact preview/code viewer where useful.
4. Add Vitest coverage for the API client, SSE framing/parser, model selection,
   timeline, and artifact list.
5. Add loading, empty, and error states to any new panel and keep the sovereignty
   display screenshot-ready.
6. Reconcile the future feature-directory plan in `CHECKLIST.md` with the current
   component structure before doing a large move; avoid mixing a structural rename
   with behavior changes.

## 6. Coordination rules

- Create a branch from the baseline commit: `feat/frontend-<short>`.
- Keep backend contract changes in a separate commit/PR, and update
  `frontend/src/api/types.ts`, this document, and backend schemas together when a
  response changes.
- Do not add cloud calls, telemetry, or external font/CDN dependencies. The app must
  remain usable from local files and the local backend in air-gap mode.
- Never commit `.env`, model weights, `data/`, uploads, artifacts, `node_modules`,
  or `.venv`.
- Before handing off a frontend PR, run `npm run lint`, `npm run typecheck`, and
  `npm run build` from `frontend/`.
