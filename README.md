# Sovereign Workbench

**A self-hosted, air-gapped AI workbench for confidential industrial knowledge work.**
Open-weight LLMs + local tools, running entirely on your own hardware — nothing leaves
the premises.

> Response to **Smart India Hackathon 2026 · SIH26117**
> “Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for
> Confidential Industrial Work” (Mangalore Refinery and Petrochemicals Limited).

---

## Why

Refineries, PSUs, defence-linked manufacturing and government offices generate a lot
of routine but sensitive knowledge work — approval notes, board decks, engineering
calculations, internal tooling code, review of scanned drawings and inspection
reports. That work **can’t** go through cloud AI assistants because policy keeps the
data on-premises. So people either do it by hand, or quietly paste confidential
material into public tools.

Sovereign Workbench is the on-premises assistant they *can* use: it plans multi-step
work, calls local tools, reads scanned documents and drawings, and returns **real
deliverables** — a `.docx` approval note, a `.pptx`, an `.xlsx`, verified code — with
a visible audit trail proving no external calls were made.

## What it does

- **Agentic, not just chat.** Plans → calls tools → observes → iterates.
- **Real deliverables.** Word / PowerPoint / Excel files, working code, calculations
  with the steps shown.
- **Multimodal.** Scanned PDFs, handwritten notes, engineering drawings, photos (local
  OCR + vision).
- **Grounded.** Answers cite your own manuals, SOPs and past correspondence (local RAG).
- **Model-agnostic.** Several open-weight models, auto-selected per task; add new ones
  without redesign.
- **Sovereign.** Air-gap mode blocks and logs all external calls — provable, not claimed.

## Architecture (short version)

```
 React + Vite (frontend)  ──REST/SSE──▶  FastAPI (backend)
                                            ├── Agent core (plan/act/observe)
                                            ├── Tools: fs · code_exec · xlsx · doc_search · ocr_vision
                                            ├── LLM provider + registry + router
                                            ├── RAG (local embeddings + vector store)
                                            ├── Deliverables (docx/pptx/xlsx)
                                            └── EgressGuard + AuditLog
```

Full detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
Sovereignty model: [`docs/SOVEREIGNTY.md`](docs/SOVEREIGNTY.md) ·
Models: [`docs/MODELS.md`](docs/MODELS.md) ·
Context: [`CONTEXT.md`](CONTEXT.md) · Plan: [`CHECKLIST.md`](CHECKLIST.md)

## Minimum hardware

Target: Intel i3 (3rd gen) · **8 GB RAM** · **2 GB GPU** · no internet required after setup.
The minimum-tier models are small quantized weights (see `docs/MODELS.md`); performance
on that target hardware still needs verification. Bigger machines
use bigger local models; optional cloud API providers exist as a fallback and are
**disabled in air-gap mode**.

## Quickstart

These commands work from a Git checkout, an extracted archive, or a directory copied
onto the target machine. The setup scripts do not require Git metadata. The only
intentional online step is downloading Python/Node packages and local model weights;
complete it before the machine is disconnected.

```bash
# 1. Create the venv and install the declared backend/frontend dependencies.
#    This also copies .env.example to .env when .env is absent.
./scripts/bootstrap.sh

# 2. Review the model selection, then pull the minimum-tier Ollama models.
./scripts/pull-models.sh --dry-run
./scripts/pull-models.sh

# 3. Run backend + frontend together (backend :8000, frontend :5173).
./scripts/dev.sh

# 4. With the backend running, prove the local API and socket state.
./scripts/verify-airgap.sh
```

`bootstrap.sh` installs the backend package in editable mode from
`backend/pyproject.toml` and installs the frontend with `npm ci`. If dependencies are
already cached, use `./scripts/bootstrap.sh --offline`; it never contacts package
indexes in that mode.
The default backend extras include `dev,ocr`; install host `tesseract-ocr` and
`poppler-utils` for image/scanned-PDF OCR when running without Docker (the backend
image includes both). On Debian/Ubuntu: `sudo apt-get install tesseract-ocr poppler-utils`.

`pull-models.sh` reads only non-remote `ollama` entries from `models/models.toml`. It
uses a host Ollama installation when available. Without one, it starts the Compose
`ollama` service and stores weights in the `ollama-models` volume. Use
`OLLAMA_USE_COMPOSE=1 ./scripts/pull-models.sh` when both are installed and the Compose
volume is the intended runtime. `--all-local` pulls standard and large Ollama entries;
the default is the minimum tier. The CPU minimum tier intentionally uses the existing
hashing embedder and does not download the optional embedding model. Ollama publishes
the vision model as `moondream`; the pull script makes a local `moondream2` alias to
match the existing registry entry.

`dev.sh` starts an installed host Ollama temporarily when needed, or reuses an already
running host/Compose service. If neither runtime is available, the UI/API still start
for development but model tasks cannot run until Ollama is started.

Or with Docker:

```bash
# Pull models into the Compose volume before disconnecting the host.
OLLAMA_USE_COMPOSE=1 ./scripts/pull-models.sh

# CPU deployment. The services bind to localhost only.
docker compose up --build --wait

# NVIDIA GPU deployment (requires the NVIDIA Container Toolkit).
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build --wait
```

The GPU override assigns the Ollama service one NVIDIA GPU; the backend and frontend
remain ordinary CPU containers. The Compose backend uses a fixed private address for
Ollama because the application egress guard deliberately treats unknown DNS names as
external. Published ports are loopback-only by default: `8000` for the backend,
`5173` for the frontend, and `11434` for Ollama. Override them with environment
variables when necessary.

## Development

```bash
make lint             # backend Ruff/Black/mypy + frontend lint/typecheck
make test             # backend pytest + frontend vitest
make build            # frontend build + Docker Compose images
make compose-config   # validate CPU and GPU Compose syntax
make verify-airgap    # API health/egress + established socket check
```

- Backend: Python 3.11 or 3.12 (FastAPI, Pydantic v2, SQLAlchemy, SQLite)
- Frontend: Node 20+ (React 18, Vite, TypeScript strict, Tailwind)
- Runtime: Ollama (default) / llama.cpp / any OpenAI-compatible endpoint

The frontend package declares `dev`, `build`, `lint`, `format`, `typecheck`, and
`test` (Vitest + jsdom + Testing Library) and ships a lockfile for reproducible
installs. CI keeps `AIRGAP=true` for backend tests and never pulls model weights.

### Backend verification

```bash
make backend-lint
make backend-test
# From backend/, enforce the same core coverage threshold as CI:
../.venv/bin/pytest --cov=sovereign_workbench.core --cov-fail-under=70
```

The suite exercises real scanned-PDF OCR → DOCX, office-file downloads, computed
spreadsheet cells, code execution/output limits, model protocol/routing, document
citations, and durable task reconnect/cancellation. OCR integration requires the
host binaries above. Model responses are mocked in tests and network connections
are denied. Actual model quality and performance on the i3/8 GB machine require a
deployment run; see [`docs/BACKEND_STATUS.md`](docs/BACKEND_STATUS.md).

For stronger code isolation, pre-pull `python:3.12-slim` on a Docker-enabled host
and set `SANDBOX_BACKEND=docker`. The default `auto` uses it when available and
otherwise selects the documented best-effort subprocess driver. Docker task runs
never pull images or enable networking.

### Frontend (Rohit)

After `./scripts/bootstrap.sh`, use `make frontend` (or `npm run dev` in `frontend/`)
to start Vite on `http://127.0.0.1:5173`. The Vite proxy forwards `/api` to the backend
on `127.0.0.1:8000`; use `make backend` in a second terminal if running the services
separately. Run `make frontend-lint`, `make frontend-test`, and `make frontend-build`
for checks. The frontend owner and backend/infra owner coordinate through
[`docs/FRONTEND_HANDOFF.md`](docs/FRONTEND_HANDOFF.md).

To use the UI **without a backend** (screenshots, review on a machine with no
models), set `VITE_USE_MOCK=true` in `frontend/.env.local`; the client then answers
every route from `frontend/scripts/seed.ts`, including a scripted agent stream.
The two-minute demo script and screenshot shot list are in
[`docs/DEMO.md`](docs/DEMO.md).

## Stable local API

The coordination boundary between the backend/infra and frontend owners is the
implemented `/api` contract in
[`docs/FRONTEND_HANDOFF.md`](docs/FRONTEND_HANDOFF.md).
The setup tooling relies only on `GET /api/health` and `GET /api/audit/egress`, so it can
verify sovereignty without coupling to agent internals. The current UI streams a run
through `POST /api/chat` (SSE) and uses the same `/api/models`, `/api/tasks`,
`/api/documents`, `/api/artifacts`, and audit endpoint families listed in the checklist.
The checklist retains the original target plan; the handoff document records the
routes and response shapes currently served by the code.
Keep new setup and UI work at this boundary rather than importing backend modules.

Read [`CONTEXT.md`](CONTEXT.md) before contributing, then pick a task from
[`CHECKLIST.md`](CHECKLIST.md). See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Licence

Apache-2.0 © the Sovereign Workbench contributors. See [`LICENSE`](LICENSE).
Third-party runtime licences include the named certifi/pathspec MPL exceptions
and separately installed OCR programs described in
[`ADR 0002`](docs/adr/0002-backend-runtime-and-recovery.md).
