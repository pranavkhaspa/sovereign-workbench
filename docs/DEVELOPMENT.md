# Development and deployment runbook

This runbook covers the repository's current setup surface. It intentionally leaves
application implementation work to the tasks in [`CHECKLIST.md`](../CHECKLIST.md).

## Local development

1. Run `./scripts/bootstrap.sh` from the repository root. It creates `.venv`, installs
   dependencies declared by `backend/pyproject.toml`, installs frontend dependencies,
   and creates `.env` from `.env.example` if needed.
2. Run `./scripts/pull-models.sh --dry-run` to inspect the minimum-tier Ollama rows.
3. Run `./scripts/pull-models.sh` while the machine still has network access. Model
   downloads are the deliberate setup exception to the air-gap rule.
4. Run `./scripts/dev.sh`. It starts Uvicorn on `127.0.0.1:8000` and Vite on
   `127.0.0.1:5173`, and stops both children on Ctrl-C. When Ollama is installed but
   not already running, the script starts it temporarily too.
5. Run `./scripts/verify-airgap.sh` with both services running.

For an offline package install, use `./scripts/bootstrap.sh --offline` only after the
required pip/npm artifacts have been cached. `bootstrap.sh` does not attempt to upgrade
pip in offline mode. `SKIP_FRONTEND=1` or `--skip-frontend` is useful for backend-only
CI and air-gapped backend maintenance. The default backend extras include OCR Python
packages; install the host Tesseract binary separately for OCR in local development.

## Compose deployment

The CPU file has three services:

- `ollama` stores weights in the named `ollama-models` volume.
- `backend` stores its SQLite database, uploads, workspace, artifacts, and vector data
  in the named `workbench-data` volume.
- `frontend` serves the built SPA and proxies `/api` and SSE to `backend`.

Use `OLLAMA_USE_COMPOSE=1 ./scripts/pull-models.sh` before `docker compose up` when
weights should live in the Compose volume. The GPU override adds an NVIDIA device
reservation only to Ollama. `docker compose config --quiet` and
`docker compose -f docker-compose.yml -f docker-compose.gpu.yml config --quiet` are the
quick configuration checks used by CI.

The containers share a private Docker bridge with fixed addresses. The backend points to
Ollama by its private IP so `EgressGuard` can classify the connection as local; the
frontend's Nginx proxy may still use the service name because it is not an application
HTTP client. The Compose network is not a host firewall. Pair deployment with the
organisation's firewall or an offline host/network policy before handling confidential
data.

## Checks and package scripts

| Command | What it runs |
| --- | --- |
| `make backend-lint` | Ruff, Black `--check`, and mypy against `backend/` |
| `make backend-test` | `pytest -q` from the backend package |
| `make frontend-lint` | The frontend's declared `lint` and `typecheck` scripts |
| `make frontend-build` | The frontend's declared `build` script |
| `make lint` | Backend and frontend checks above |
| `make test` | Backend tests and a no-op frontend test check until a test script exists |
| `make build` | Frontend build followed by `docker compose build` |
| `make verify-airgap` | Stable API checks plus established socket inspection |

The frontend has a committed `package-lock.json`, so bootstrap, CI, and the frontend
image use `npm ci`. There is no frontend test script yet; when adding one, update the
package manifest, lockfile, `Makefile`, and workflow together.

## Stable API coordination

The frontend/backend boundary is the implemented `/api` contract in
[`FRONTEND_HANDOFF.md`](FRONTEND_HANDOFF.md). The original target table remains in
[`CHECKLIST.md §4`](../CHECKLIST.md#api-contract) for planning history.
The air-gap verifier intentionally uses only:

- `GET /api/health` and its `airgap`/`status` fields;
- `GET /api/audit/egress` and its `airgap`, `blocked`, `allowed_local`, and
  `external_allowed` fields.

The live UI currently uses `POST /api/chat` for its SSE stream, alongside the model,
task, document, artifact, and audit paths in the checklist. Keep setup scripts dependent
only on the health/egress portion so API implementation work can proceed independently.

## Air-gap verification limits

`verify-airgap.sh` fails if the API is unavailable, if `AIRGAP` is false, if the backend
reports allowed external calls, or if the host socket table exposes an established
non-loopback/non-private peer. `--api-only` is available inside restricted containers
where `/proc` or `ss` is not visible, but host-level socket inspection is the stronger
check. The application guard blocks and audits attempted external HTTP requests; it is
not a replacement for a host firewall.
