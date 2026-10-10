# Sovereign Workbench backend

The FastAPI package for [Sovereign Workbench](../README.md). Its `pyproject.toml`
uses this file for package metadata.

From the repository root, run `./scripts/bootstrap.sh` to install the backend in
an editable virtual environment, then `make backend` to serve the API at
`http://127.0.0.1:8000/api/health`. See
[the frontend handoff](../docs/FRONTEND_HANDOFF.md) for routes and payloads.

Backend checks: `make backend-test` and `make backend-lint` from the repository root.
