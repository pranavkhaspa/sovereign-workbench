# Backend completion and release gates

Updated: 2026-10-10. Scope: backend, CI, setup and the API handoff.

## Implemented and exercised

- Local model registry, installed-model probing, hardware-ceiling routing,
  code/general/vision selection, OpenAI-compatible requests and real token streaming.
- Schema-informed planning, observations, bounded replanning, permission checks,
  timeouts and a single active run to limit memory usage.
- Persisted tasks, paginated history, durable SSE events/tokens, numeric replay
  cursors, disconnect-independent execution, cancellation and crash recovery.
- File/text/PDF/DOCX/image/spreadsheet ingestion and retrieval with source citations.
  Mixed PDFs OCR only image pages; PDF rendering is page-at-a-time.
- Downloadable approval notes, reports, presentations, computed Excel workbooks,
  source code and execution logs. Artifact snapshots cannot overwrite earlier ones.
- Safe arithmetic with intermediate steps and bounded/no-network subprocess execution.
- Docker execution driver with pre-pulled images, no network, non-root execution,
  read-only source, resource limits and cleanup on timeout/cancellation.
- Guarded HTTP transport, proxy-environment isolation, cache-only offline semantic
  embeddings, auditable egress and restart-persistent counters.

## Verification evidence

- Offline backend suite: **59 passed**, **1 skipped** (live Docker isolation),
  **78.39% core coverage**. The OCR test runs real Tesseract/Poppler on a generated
  scanned PDF and downloads/parses the resulting DOCX. LLM responses are mocked.
- Frontend baseline lint/typecheck/build passed; production JS is about **71 KB gzip**.
- Python and frontend licence checks passed. Named MPL exceptions are documented in
  ADR 0002 and checked separately, not globally allowed.
- CPU and GPU Compose configurations validate with Docker Compose v2.
- Shell syntax checks, embedded Python syntax checks and model-pull dry-run pass.
- Live Uvicorn API smoke: upload → approval DOCX download and supplied Python →
  source/execution-log downloads passed with no model running. The deterministic
  fallback was exercised. `verify-airgap.sh --api-only` passed with zero allowed
  external requests; this is not the full host socket scan.

The local suite does not certify live LLM output quality or minimum-machine latency.

## Before calling the entire project 100% complete

1. **Remote CI:** push the changes through the normal review workflow and confirm
   Backend CI, Frontend CI, Docker, CodeQL and Licence checks. The current environment
   has no authenticated GitHub CLI session, so remote logs/runs cannot be verified here.
2. **Docker runtime:** this sandbox does not permit mount namespaces. On a Docker host:
   `docker pull python:3.12-slim`, then from `backend/` run
   `SW_TEST_DOCKER=1 ../.venv/bin/pytest tests/test_docker_sandbox.py`.
   Run `docker compose up --build --wait` for the image/stack smoke check. CI now runs
   the Docker isolation test explicitly after provisioning its image.
3. **Live local models:** run `./scripts/pull-models.sh`, refresh `/api/models`, and
   exercise code, general and image tasks with actual weights. No model weights were
   downloaded during backend tests.
4. **Minimum hardware:** repeat the demo on the i3/8 GB/2 GB GPU machine. Record peak
   memory, first-token latency, total duration and `scripts/verify-airgap.sh` output.
5. **Frontend owner:** finish cancel/resume wiring, document management, accessibility,
   UI tests and demo assets using `docs/FRONTEND_HANDOFF.md`.

Run a single Uvicorn process. Strong code isolation requires the Docker driver;
the subprocess driver is best-effort, as described in `docs/SOVEREIGNTY.md`.
Optional stretch work (multi-user auth, TTS, reranking, PaddleOCR) is outside the
minimum deliverable and remains separately tracked in `CHECKLIST.md`.
