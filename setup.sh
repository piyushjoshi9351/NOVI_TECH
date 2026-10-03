#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/venv"
ROOT_ENV="$ROOT_DIR/.env"
BACKEND_ENV="$BACKEND_DIR/.env"

WITH_FRONTEND=0
SKIP_DEPS=0
SKIP_DOCKER=0
NO_INIT=0
DB_RESET=0

C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YLW=$'\033[33m'; C_BLU=$'\033[34m'
C_BLD=$'\033[1m'; C_RST=$'\033[0m'
if [ ! -t 1 ]; then C_RED=""; C_GRN=""; C_YLW=""; C_BLU=""; C_BLD=""; C_RST=""; fi

log()  { printf "${C_BLU}[NOVI]${C_RST} %s\n" "$*"; }
ok()   { printf "${C_GRN}[ OK ]${C_RST} %s\n" "$*"; }
warn() { printf "${C_YLW}[WARN]${C_RST} %s\n" "$*"; }
err()  { printf "${C_RED}[ERROR]${C_RST} %s\n" "$*" >&2; }
die()  { err "$*"; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

venv_python() {
  if [ -x "$VENV_DIR/bin/python" ]; then
    printf '%s' "$VENV_DIR/bin/python"
  elif [ -x "$VENV_DIR/Scripts/python.exe" ]; then
    printf '%s' "$VENV_DIR/Scripts/python.exe"
  else
    printf '%s' "$(command -v python3 || command -v python)"
  fi
}

port_open() {
  local host="$1" port="$2"
  if command_exists timeout; then
    timeout 3 bash -c "cat < /dev/null > /dev/tcp/$host/$port" >/dev/null 2>&1
  else
    bash -c "cat < /dev/null > /dev/tcp/$host/$port" >/dev/null 2>&1
  fi
}

wait_port() {
  local host="$1" port="$2" name="$3" tries="${4:-45}" i
  log "Waiting for $name on $host:$port ..."
  for i in $(seq 1 "$tries"); do
    if port_open "$host" "$port"; then
      ok "$name is up"
      return 0
    fi
    sleep 2
  done
  warn "$name did not become ready in time — continuing anyway"
}

banner() {
  printf "${C_BLD}%s${C_RST}\n" "========================================="
  printf "${C_BLD}   NOVI - AI Student Mentor  ${C_RST}\n"
  printf "${C_BLD}%s${C_RST}\n" "========================================="
}

usage() {
  cat <<'EOF'
Usage: ./setup.sh [options]

Sets up and runs NOVI (Docker services + backend + optional frontend).

Options:
  --frontend     also install and start the Next.js frontend (port 3000)
  --no-docker    skip starting Docker services
  --skip-deps    skip pip install (keeps existing venv)
  --no-init      skip database init (tables + seeds)
  --reset        drop and recreate database tables before init
  -h, --help     show this help

Run from the repo root (this script's directory).
On Windows: run via "bash setup.sh" or Git Bash.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --frontend)   WITH_FRONTEND=1 ;;
    --no-docker)  SKIP_DOCKER=1 ;;
    --skip-deps)  SKIP_DEPS=1 ;;
    --no-init)    NO_INIT=1 ;;
    --reset)      DB_RESET=1 ;;
    -h|--help)    usage; exit 0 ;;
    *)            die "unknown option: $1" ;;
  esac
  shift
done

check_docker() {
  if [ "$SKIP_DOCKER" -eq 1 ]; then return; fi
  command_exists docker || die "docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop"
  if docker info >/dev/null 2>&1; then
    ok "Docker is running"
    return
  fi
  warn "Docker daemon is not reachable."
  warn "Start Docker Desktop and wait for the whale icon to show 'Running',"
  warn "then press Enter here (or press Ctrl-C to abort)."
  local resp
  read -r -p "  Press Enter when Docker is running... " resp
  docker info >/dev/null 2>&1 || die "Docker still not reachable. Aborting."
  ok "Docker is running"
}

gemini_key() {
  grep -E '^GEMINI_API_KEY=' "$BACKEND_ENV" 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '" ' 
}

ensure_envs() {
  if [ -f "$BACKEND_ENV" ]; then
    ok "backend/.env found"
  else
    if [ -f "$BACKEND_DIR/.env.example" ]; then
      cp "$BACKEND_DIR/.env.example" "$BACKEND_ENV"
      warn "Created backend/.env from template — edit it to add your Gemini key."
    fi
  fi

  if [ ! -f "$ROOT_ENV" ]; then
    if [ -f "$ROOT_DIR/.env.example" ]; then
      cp "$ROOT_DIR/.env.example" "$ROOT_ENV"
    else
      : > "$ROOT_ENV"
    fi
    warn "Created root .env from template."
  fi

  local key
  key="$(gemini_key)"
  if [ -n "$key" ] && [ "$key" != "your_gemini_api_key" ] && [ "$key" != "your_gemini_api_key_here" ]; then
    if grep -q '^GEMINI_API_KEY=' "$ROOT_ENV"; then
      sed -i.bak "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$key|" "$ROOT_ENV"
      rm -f "$ROOT_ENV.bak"
    else
      printf '\nGEMINI_API_KEY=%s\n' "$key" >> "$ROOT_ENV"
    fi
    ok "GEMINI_API_KEY synced into root .env (used by docker-compose)"
  else
    warn "No valid GEMINI_API_KEY found — AI features will fall back to Ollama."
  fi

  if ! grep -q '^LETTA_SERVER_PASSWORD=' "$ROOT_ENV"; then
    local pw
    pw="$(openssl rand -hex 16 2>/dev/null || { date +%s%N | md5sum | cut -d' ' -f1; })"
    printf 'LETTA_SERVER_PASSWORD=%s\n' "$pw" >> "$ROOT_ENV"
    ok "Generated LETTA_SERVER_PASSWORD in root .env"
  fi
}

start_services() {
  if [ "$SKIP_DOCKER" -eq 1 ]; then return; fi
  local services=(postgres redis letta)
  local start_mysql=1
  if port_open localhost 3306; then
    start_mysql=0
    warn "Port 3306 is already in use; using the existing MySQL service."
  else
    services=(mysql "${services[@]}")
  fi

  log "Starting Docker infrastructure (${services[*]})..."
  (cd "$ROOT_DIR" && compose up -d "${services[@]}")
  wait_port localhost 8283 "Letta server"
  wait_port localhost 5432 "Letta Postgres"
  wait_port localhost 6379 "Redis"
  if [ "$start_mysql" -eq 1 ]; then
    wait_port localhost 3306 "MySQL"
  fi
}

check_mysql() {
  wait_port localhost 3306 "MySQL"
}

ensure_venv() {
  if [ -d "$VENV_DIR" ]; then
    ok "venv found at $VENV_DIR"
    return
  fi
  command_exists python3 || command_exists python || die "python3 not found. Install Python 3.10+ first."
  log "Creating virtual environment at $VENV_DIR ..."
  python3 -m venv "$VENV_DIR" || python -m venv "$VENV_DIR"
  ok "venv created"
}

install_deps() {
  if [ "$SKIP_DEPS" -eq 1 ]; then return; fi
  local py
  py="$(venv_python)"
  log "Installing Python requirements..."
  "$py" -m pip install --upgrade pip -q
  "$py" -m pip install -r "$BACKEND_DIR/requirements.txt" -q
  ok "Python dependencies installed"
}

init_db() {
  if [ "$NO_INIT" -eq 1 ]; then return; fi
  local py
  py="$(venv_python)"
  log "Initializing database (tables + seed data)..."
  if [ "$DB_RESET" -eq 1 ]; then
    (cd "$BACKEND_DIR" && "$py" -m app.db.init_db --reset)
  else
    (cd "$BACKEND_DIR" && "$py" -m app.db.init_db)
  fi
  ok "Database initialized"
}

run_frontend() {
  command_exists npm || die "npm not found. Install Node.js 18+ first."
  log "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
  log "Starting Next.js frontend on http://localhost:3000 ..."
  (cd "$FRONTEND_DIR" && exec npm run dev) &
}

run_backend() {
  local py
  py="$(venv_python)"
  log "Starting NOVI backend on http://localhost:8000  (Ctrl-C to stop)"
  (cd "$BACKEND_DIR" && exec "$py" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000)
}

banner
ensure_envs
check_docker
start_services
check_mysql
ensure_venv
install_deps
init_db
run_frontend
run_backend
