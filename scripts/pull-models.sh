#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY_PATH="${MODEL_REGISTRY_PATH:-$ROOT_DIR/models/models.toml}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="${SYSTEM_PYTHON_BIN:-python3}"
fi

DRY_RUN=0
ALL_LOCAL=0
TIER=min
REQUESTED_MODELS=()
OLLAMA_USE_COMPOSE="${OLLAMA_USE_COMPOSE:-0}"
OLLAMA_PID=""

usage() {
    cat <<'EOF'
Usage: ./scripts/pull-models.sh [options]

Pull local Ollama models from models/models.toml. This is the deliberate online
setup step; it is not run by bootstrap and it should be completed before an
air-gapped deployment is disconnected.

Options:
  --dry-run              Print the selected models without pulling them.
  --all-local            Include standard and large local Ollama models.
  --tier NAME            Pull one tier (default: min).
  --model ID_OR_NAME     Pull one registry id or model_name (repeatable).
  -h, --help             Show this help.

The script uses a local `ollama` CLI when available. If it is not installed, it
uses the `ollama` service from docker-compose.yml; start the stack or let the
script start that service first.
EOF
}

die() {
    printf 'pull-models: %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$OLLAMA_PID" ]] && kill -0 "$OLLAMA_PID" 2>/dev/null; then
        kill "$OLLAMA_PID" 2>/dev/null || true
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

while (($#)); do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        --all-local)
            ALL_LOCAL=1
            ;;
        --tier)
            (($# >= 2)) || die "--tier requires a value"
            TIER="$2"
            shift
            ;;
        --model)
            (($# >= 2)) || die "--model requires a value"
            REQUESTED_MODELS+=("$2")
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1 (use --help for usage)"
            ;;
    esac
    shift
done

[[ -f "$REGISTRY_PATH" ]] || die "model registry not found: $REGISTRY_PATH"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python is required to read the model registry"

MODEL_ROWS_OUTPUT="$(
    "$PYTHON_BIN" - "$REGISTRY_PATH" "$TIER" "$ALL_LOCAL" "${REQUESTED_MODELS[@]}" <<'PY'
import sys
import tomllib
from pathlib import Path

registry_path = Path(sys.argv[1])
tier = sys.argv[2]
all_local = sys.argv[3] == "1"
requested = sys.argv[4:]
entries = tomllib.loads(registry_path.read_text(encoding="utf-8")).get("model", [])

if requested:
    selected = []
    for item in requested:
        matches = [
            entry
            for entry in entries
            if entry.get("id") == item or entry.get("model_name") == item
        ]
        if not matches:
            raise SystemExit(f"model id/name not found in registry: {item}")
        selected.extend(matches)
else:
    selected = [
        entry
        for entry in entries
        if entry.get("provider") == "ollama"
        and not entry.get("remote", False)
        and (all_local or entry.get("tier") == tier)
    ]

seen = set()
for entry in selected:
    model_name = entry.get("model_name")
    if entry.get("provider") != "ollama" or entry.get("remote", False) or not model_name:
        continue
    if model_name in seen:
        continue
    seen.add(model_name)
    print(f"{entry.get('id', model_name)}\t{model_name}")

if not seen:
    raise SystemExit("no local Ollama models matched the selection")
PY
)"
mapfile -t MODEL_ROWS <<<"$MODEL_ROWS_OUTPUT"

printf 'pull-models: selected models:\n'
for row in "${MODEL_ROWS[@]}"; do
    printf '  %s\n' "${row//$'\t'/ -> }"
    if [[ "${row#*$'\t'}" == "moondream2" ]]; then
        printf '    (pull moondream:latest and create a local moondream2 alias)\n'
    fi
done

if ((DRY_RUN == 1)); then
    exit 0
fi

LOCAL_OLLAMA=0
if [[ "$OLLAMA_USE_COMPOSE" != "1" ]] && command -v ollama >/dev/null 2>&1; then
    LOCAL_OLLAMA=1
fi

if ((LOCAL_OLLAMA == 1)); then
    if [[ -n "${OLLAMA_BASE_URL:-}" && -z "${OLLAMA_HOST:-}" ]]; then
        OLLAMA_HOST="$($PYTHON_BIN - "${OLLAMA_BASE_URL}" <<'PY'
import sys
from urllib.parse import urlparse

parsed = urlparse(sys.argv[1])
if not parsed.hostname:
    raise SystemExit("OLLAMA_BASE_URL has no hostname")
print(f"{parsed.hostname}:{parsed.port or 11434}")
PY
        )"
        export OLLAMA_HOST
    fi

    if ! ollama list >/dev/null 2>&1; then
        if [[ "${START_OLLAMA:-1}" != "1" ]]; then
            die "Ollama is installed but not reachable; start 'ollama serve' or set START_OLLAMA=1"
        fi
        printf 'pull-models: starting a temporary local Ollama server\n'
        ollama serve >/tmp/sovereign-workbench-ollama.log 2>&1 &
        OLLAMA_PID=$!
        ready=0
        for _ in {1..30}; do
            if ollama list >/dev/null 2>&1; then
                ready=1
                break
            fi
            sleep 1
        done
        ((ready == 1)) || die "Ollama did not become ready; see /tmp/sovereign-workbench-ollama.log"
    fi
else
    command -v docker >/dev/null 2>&1 || die "ollama is not installed and docker is unavailable"
    docker compose --project-directory "$ROOT_DIR" config --services >/dev/null \
        || die "docker compose is unavailable or the Compose file is invalid"
    if ! docker compose --project-directory "$ROOT_DIR" ps --status running --services \
        | "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if "ollama" in sys.stdin.read().split() else 1)'; then
        printf 'pull-models: starting the Compose Ollama service\n'
        docker compose --project-directory "$ROOT_DIR" up -d ollama
    fi
    ready=0
    for _ in {1..30}; do
        if docker compose --project-directory "$ROOT_DIR" exec -T ollama ollama list >/dev/null 2>&1; then
            ready=1
            break
        fi
        sleep 1
    done
    ((ready == 1)) || die "Compose Ollama service did not become ready"
fi

model_present_local() {
    local model_name=$1
    ollama list | "$PYTHON_BIN" -c '
import sys
target = sys.argv[1]
names = {target, f"{target}:latest"}
raise SystemExit(0 if any(line.split() and line.split()[0] in names for line in sys.stdin) else 1)
' "$model_name"
}

model_present_compose() {
    local model_name=$1
    docker compose --project-directory "$ROOT_DIR" exec -T ollama ollama list \
        | "$PYTHON_BIN" -c '
import sys
target = sys.argv[1]
names = {target, f"{target}:latest"}
raise SystemExit(0 if any(line.split() and line.split()[0] in names for line in sys.stdin) else 1)
' "$model_name"
}

for row in "${MODEL_ROWS[@]}"; do
    model_name="${row#*$'\t'}"
    pull_name="$model_name"
    if [[ "$model_name" == "moondream2" ]]; then
        # The published Ollama model is `moondream`, while this registry expects
        # `moondream2`. Copy a local alias so inference uses the registry name.
        pull_name="moondream:latest"
    fi
    if ((LOCAL_OLLAMA == 1)); then
        if model_present_local "$model_name"; then
            printf 'pull-models: already present: %s\n' "$model_name"
            continue
        fi
        if ! model_present_local "$pull_name"; then
            printf 'pull-models: pulling %s\n' "$pull_name"
            ollama pull "$pull_name"
        fi
        if [[ "$pull_name" != "$model_name" ]]; then
            printf 'pull-models: aliasing %s as %s\n' "$pull_name" "$model_name"
            ollama cp "$pull_name" "$model_name"
        fi
    else
        if model_present_compose "$model_name"; then
            printf 'pull-models: already present: %s\n' "$model_name"
            continue
        fi
        if ! model_present_compose "$pull_name"; then
            printf 'pull-models: pulling %s through Compose\n' "$pull_name"
            docker compose --project-directory "$ROOT_DIR" exec -T ollama ollama pull "$pull_name"
        fi
        if [[ "$pull_name" != "$model_name" ]]; then
            printf 'pull-models: aliasing %s as %s through Compose\n' "$pull_name" "$model_name"
            docker compose --project-directory "$ROOT_DIR" exec -T ollama ollama cp "$pull_name" "$model_name"
        fi
    fi
done

printf 'pull-models: complete; disconnect the host from the network before air-gapped operation\n'
