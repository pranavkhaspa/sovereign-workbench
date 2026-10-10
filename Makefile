# Sovereign Workbench — local developer tasks
SHELL := /bin/bash
.DEFAULT_GOAL := help

ROOT := $(abspath .)
BACKEND := backend
FRONTEND := frontend
VENV := $(ROOT)/.venv
PY := $(VENV)/bin/python
NPM := npm

.PHONY: help
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: bootstrap
bootstrap: ## Create the venv and install backend/frontend dependencies
	./scripts/bootstrap.sh

.PHONY: models
models: ## Pull the minimum-tier local Ollama models
	./scripts/pull-models.sh

.PHONY: models-dry-run
models-dry-run: ## Show the models that would be pulled
	./scripts/pull-models.sh --dry-run

.PHONY: dev
dev: ## Run backend and frontend together with local hot reload
	./scripts/dev.sh

.PHONY: backend
backend: ## Run only the backend with reload
	@test -x "$(PY)" || { echo "Run make bootstrap first" >&2; exit 1; }
	AIRGAP=$${AIRGAP:-true} PYTHONPATH=$(ROOT)/backend/src "$(PY)" -m uvicorn sovereign_workbench.main:app --app-dir $(ROOT)/backend/src --reload --host $${HOST:-127.0.0.1} --port $${BACKEND_PORT:-8000}

.PHONY: frontend
frontend: ## Run only the frontend with Vite
	@test -d "$(FRONTEND)/node_modules" || { echo "Run make bootstrap first" >&2; exit 1; }
	cd $(FRONTEND) && $(NPM) run dev -- --host $${HOST:-127.0.0.1} --port $${FRONTEND_PORT:-5173} --strictPort

.PHONY: backend-lint
backend-lint: ## Run backend Ruff, Black, and mypy checks
	@test -x "$(PY)" || { echo "Run make bootstrap first" >&2; exit 1; }
	cd $(BACKEND) && ../.venv/bin/ruff check .
	cd $(BACKEND) && ../.venv/bin/black --check .
	cd $(BACKEND) && ../.venv/bin/mypy src

.PHONY: frontend-lint
frontend-lint: ## Run the frontend's declared lint and typecheck scripts
	@test -d "$(FRONTEND)/node_modules" || { echo "Run make bootstrap first" >&2; exit 1; }
	cd $(FRONTEND) && $(NPM) run lint
	cd $(FRONTEND) && $(NPM) run typecheck

.PHONY: lint
lint: backend-lint frontend-lint ## Run backend and frontend lint/type checks

.PHONY: fix
fix: ## Auto-format the backend
	@test -x "$(PY)" || { echo "Run make bootstrap first" >&2; exit 1; }
	cd $(BACKEND) && ../.venv/bin/ruff check --fix .
	cd $(BACKEND) && ../.venv/bin/black .

.PHONY: backend-test
backend-test: ## Run the backend pytest suite
	@test -x "$(PY)" || { echo "Run make bootstrap first" >&2; exit 1; }
	cd $(BACKEND) && ../.venv/bin/pytest -q

.PHONY: frontend-test
frontend-test: ## Run frontend tests when a test script is declared
	@if $(NPM) --prefix $(FRONTEND) pkg get scripts.test | python3 -c 'import json, sys; value=json.load(sys.stdin).get("test"); raise SystemExit(0 if value and value != "undefined" else 1)'; then \
		$(NPM) --prefix $(FRONTEND) run test; \
	else \
		echo "frontend: no test script declared; skipping"; \
	fi

.PHONY: test
test: backend-test frontend-test ## Run tests available in the current package manifests

.PHONY: frontend-build
frontend-build: ## Build the frontend using its package script
	@test -d "$(FRONTEND)/node_modules" || { echo "Run make bootstrap first" >&2; exit 1; }
	cd $(FRONTEND) && $(NPM) run build

.PHONY: build
build: frontend-build ## Build the frontend and Compose images
	docker compose build

.PHONY: compose-config
compose-config: ## Validate CPU and GPU Compose files
	docker compose config --quiet
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml config --quiet

.PHONY: verify-airgap
verify-airgap: ## Check the stable API and established sockets for egress
	./scripts/verify-airgap.sh

.PHONY: clean
clean: ## Remove local virtualenv, caches, and frontend build output
	rm -rf $(VENV) $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache $(BACKEND)/.mypy_cache
	rm -rf $(FRONTEND)/node_modules $(FRONTEND)/dist
