#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PY="$VENV_DIR/bin/python"
HOST="${HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
RELOAD_FLAG="${DEV_NO_RELOAD:-0}"
BACKEND_PID=""
FRONTEND_PID=""
BACKEND_PGID=""
FRONTEND_PGID=""
OLLAMA_PID=""

die() {
    printf 'dev: %s\n' "$*" >&2
    exit 1
}

stop_children() {
    for pgid in "$BACKEND_PGID" "$FRONTEND_PGID"; do
        if [[ -n "$pgid" ]] && kill -0 -- "-$pgid" 2>/dev/null; then
            kill -TERM -- "-$pgid" 2>/dev/null || true
        fi
    done
    for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
        if [[ -n "$pid" ]]; then
            wait "$pid" 2>/dev/null || true
        fi
    done
    if [[ -n "$OLLAMA_PID" ]]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
}

on_signal() {
    stop_children
    exit 130
}
trap on_signal INT TERM

[[ -x "$PY" ]] || die "missing $PY; run ./scripts/bootstrap.sh first"
command -v npm >/dev/null 2>&1 || die "npm is required"
[[ -d "$ROOT_DIR/frontend/node_modules" ]] || die "missing frontend/node_modules; run ./scripts/bootstrap.sh first"
"$PY" -c 'import uvicorn' >/dev/null 2>&1 || die "uvicorn is not installed in the virtual environment"
[[ "$BACKEND_PORT" == "8000" ]] || die "Vite currently proxies /api to 127.0.0.1:8000; use BACKEND_PORT=8000"

ollama_url="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
ollama_ready() {
    "$PY" - "$ollama_url" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1].rstrip("/") + "/api/tags", timeout=2) as response:
    if response.status != 200:
        raise SystemExit(1)
PY
}

if ! ollama_ready; then
    if command -v ollama >/dev/null 2>&1; then
        printf 'dev: starting a temporary Ollama server at %s\n' "$ollama_url"
        OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}" \
            OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-1}" \
            OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}" \
            ollama serve &
        OLLAMA_PID=$!
        ready=0
        for _ in {1..30}; do
            if ollama_ready; then
                ready=1
                break
            fi
            sleep 1
        done
        if ((ready != 1)); then
            stop_children
            die "Ollama did not become ready at $ollama_url"
        fi
    else
        printf 'dev: Ollama is not reachable at %s; start the Compose Ollama service or install Ollama to run model tasks\n' "$ollama_url" >&2
    fi
fi

reload_args=()
if [[ "$RELOAD_FLAG" != "1" ]]; then
    reload_args+=(--reload)
fi

export PYTHONPATH="$ROOT_DIR/backend/src${PYTHONPATH:+:$PYTHONPATH}"
export AIRGAP="${AIRGAP:-true}"

printf 'dev: backend http://%s:%s/api/health\n' "$HOST" "$BACKEND_PORT"
printf 'dev: frontend http://%s:%s\n' "$HOST" "$FRONTEND_PORT"
printf 'dev: press Ctrl-C to stop the dev services\n'

backend_command=(
    "$PY" -m uvicorn sovereign_workbench.main:app
    --app-dir "$ROOT_DIR/backend/src" \
    --host "$HOST" \
    --port "$BACKEND_PORT" \
    "${reload_args[@]}"
)
frontend_command=(npm run dev -- --host "$HOST" --port "$FRONTEND_PORT" --strictPort)

if command -v setsid >/dev/null 2>&1; then
    setsid --wait "${backend_command[@]}" &
    BACKEND_PGID=$!
    BACKEND_PID=$BACKEND_PGID
else
    "${backend_command[@]}" &
    BACKEND_PID=$!
fi

(
    cd "$ROOT_DIR/frontend"
    if command -v setsid >/dev/null 2>&1; then
        exec setsid --wait "${frontend_command[@]}"
    fi
    exec "${frontend_command[@]}"
) &
FRONTEND_PID=$!
if command -v setsid >/dev/null 2>&1; then
    FRONTEND_PGID=$FRONTEND_PID
fi

status=0
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID" || status=$?
fi
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID" || status=$?
fi
stop_children
exit "$status"
