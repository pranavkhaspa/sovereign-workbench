#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BACKEND_EXTRAS="${BACKEND_EXTRAS:-dev,ocr}"
OFFLINE=0
SKIP_FRONTEND="${SKIP_FRONTEND:-0}"

usage() {
    cat <<'EOF'
Usage: ./scripts/bootstrap.sh [options]

Create the local Python environment and install the dependencies required by the
backend and frontend. Model weights are deliberately not downloaded by this command.

Options:
  --offline          Do not contact package indexes. Packages must be cached.
  --skip-frontend    Only create the Python environment (useful in backend CI).
  -h, --help         Show this help.

Environment:
  VENV_DIR=/path       Python virtual environment location.
  PYTHON_BIN=python3   Python 3.11 or 3.12 interpreter to use.
  BACKEND_EXTRAS=dev,ocr  Comma-separated backend extras to install.
  SKIP_FRONTEND=1      Same as --skip-frontend.
EOF
}

die() {
    printf 'bootstrap: %s\n' "$*" >&2
    exit 1
}

on_error() {
    local line=$1
    printf 'bootstrap: failed at line %s\n' "$line" >&2
}
trap 'on_error "$LINENO"' ERR

while (($#)); do
    case "$1" in
        --offline)
            OFFLINE=1
            ;;
        --skip-frontend)
            SKIP_FRONTEND=1
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

[[ -f "$BACKEND_DIR/pyproject.toml" ]] || die "backend/pyproject.toml is missing"
[[ -d "$FRONTEND_DIR" ]] || die "frontend directory is missing"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "$PYTHON_BIN was not found"

"$PYTHON_BIN" - <<'PY' || die "Python 3.11 or 3.12 is required by backend/pyproject.toml"
import sys

if sys.version_info[:2] not in {(3, 11), (3, 12)}:
    raise SystemExit(1)
PY

if ((SKIP_FRONTEND == 0)); then
    command -v node >/dev/null 2>&1 || die "Node.js 20+ is required (or use --skip-frontend)"
    command -v npm >/dev/null 2>&1 || die "npm is required (or use --skip-frontend)"
    node_major="$(node -p 'process.versions.node.split(".")[0]')"
    ((node_major >= 20)) || die "Node.js 20+ is required; found $(node --version)"
fi

if [[ ! -d "$VENV_DIR" ]]; then
    printf 'bootstrap: creating %s\n' "$VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PY="$VENV_DIR/bin/python"
[[ -x "$PY" ]] || die "virtual environment is missing $PY"

PIP_FLAGS=()
if ((OFFLINE == 1)); then
    PIP_FLAGS+=(--no-index)
fi

if ((OFFLINE == 0)); then
    printf 'bootstrap: upgrading pip tooling\n'
    "$PY" -m pip install --upgrade pip wheel
else
    printf 'bootstrap: offline mode; using the pip tooling already in the venv\n'
fi

install_backend_dependencies() {
    [[ -f "$BACKEND_DIR/README.md" ]] || die "backend/README.md is missing"
    "$PY" -m pip install "${PIP_FLAGS[@]}" -e "$BACKEND_DIR[$BACKEND_EXTRAS]"
}

install_backend_dependencies

if ((SKIP_FRONTEND == 1)); then
    printf 'bootstrap: frontend installation skipped\n'
else
    npm_args=(--no-audit --no-fund)
    if ((OFFLINE == 1)); then
        npm_args+=(--offline)
    fi
    if [[ -f "$FRONTEND_DIR/package-lock.json" ]]; then
        printf 'bootstrap: installing frontend dependencies with npm ci\n'
        (cd "$FRONTEND_DIR" && npm ci "${npm_args[@]}")
    else
        printf 'bootstrap: package-lock.json is absent; installing frontend dependencies with npm install\n'
        npm_args+=(--no-package-lock)
        (cd "$FRONTEND_DIR" && npm install "${npm_args[@]}")
    fi
fi

if [[ ! -f "$ROOT_DIR/.env" && -f "$ROOT_DIR/.env.example" ]]; then
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    printf 'bootstrap: copied .env.example to .env\n'
fi

printf 'bootstrap: complete\n'
printf 'bootstrap: next steps: ./scripts/pull-models.sh, then ./scripts/dev.sh\n'
