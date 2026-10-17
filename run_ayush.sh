#!/usr/bin/env bash
#
# run_ayush.sh — start the NOVI backend (FastAPI) only.
#
# Usage: ./run_ayush.sh [--skip-deps] [--no-reload] [--port 8000]
#
# Uses backend/venv if present, else the repo-root venv, else system python3.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PORT=8000
RELOAD="--reload"
SKIP_DEPS=0

C_GRN=$'\033[32m'; C_YLW=$'\033[33m'; C_RED=$'\033[31m'; C_RST=$'\033[0m'
if [ ! -t 1 ]; then C_GRN=""; C_YLW=""; C_RED=""; C_RST=""; fi

log()  { printf "${C_GRN}[OK]${C_RST} %s\n" "$*"; }
warn() { printf "${C_YLW}[WARN]${C_RST} %s\n" "$*"; }
die()  { printf "${C_RED}[ERROR]${C_RST} %s\n" "$*" >&2; exit 1; }

[ -d "$BACKEND_DIR" ] || die "backend/ not found next to this script"

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-deps) SKIP_DEPS=1 ;;
    --no-reload) RELOAD="" ;;
    --port) PORT="${2:?missing port}"; shift ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) die "unknown option: $1 (see ./run_ayush.sh --help)" ;;
  esac
  shift
done

# Pick a Python interpreter.
if [ -x "$BACKEND_DIR/venv/bin/python" ]; then
  PY="$BACKEND_DIR/venv/bin/python"
elif [ -x "$ROOT_DIR/venv/bin/python" ]; then
  PY="$ROOT_DIR/venv/bin/python"
else
  PY="$(command -v python3 || command -v python || die "no python3 found")"
  warn "No venv found — using system $PY. Consider: python3 -m venv backend/venv"
fi

log "Using Python: $PY"

# Install deps unless the user asked to skip.
if [ "$SKIP_DEPS" -eq 0 ]; then
  log "Installing requirements..."
  "$PY" -m pip install -r "$BACKEND_DIR/requirements.txt" -q
fi

# Free the port if something stale is bound to it.
if command -v ss >/dev/null 2>&1 && ss -tln 2>/dev/null | grep -q ":${PORT} "; then
  pids="$(ss -tlnp 2>/dev/null | grep ":${PORT} " | sed -E 's/.*pid=([0-9]+).*/\1/' | sort -u)"
  if [ -n "$pids" ]; then
    warn "Port $PORT is in use by PID(s): $pids — killing them"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
fi

# Run the real app (app.main:app — NOT the old legacy main:app).
log "Starting NOVI backend on http://localhost:$PORT  (Ctrl-C to stop)"
cd "$BACKEND_DIR"
exec "$PY" -m uvicorn app.main:app $RELOAD --host 0.0.0.0 --port "$PORT" --no-proxy-headers
