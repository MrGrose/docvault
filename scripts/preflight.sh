#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== lint =="
uv run ruff check .
uv run ruff format --check .
uv run mypy src

echo "== tests =="
uv run pytest -q --cov=src --cov-report=term --cov-fail-under=90

echo "== dependencies =="
uv run --with pip-audit pip-audit

echo "== static security =="
uv run --with bandit bandit -q -r src -ll

echo "== fault =="
RUN_FAULT_TESTS=1 uv run pytest tests/fault -q

echo "== api fuzz =="
PORT="${DOCVAULT_PREFLIGHT_PORT:-8111}"
REPO="$(mktemp -d)"
LOG="$(mktemp)"
cleanup() {
  if [ -n "${SERVER_PID:-}" ]; then
    pkill -P "$SERVER_PID" 2>/dev/null || true
  fi
  if [ -n "${SERVER_CHILD:-}" ]; then
    kill "$SERVER_CHILD" 2>/dev/null || true
  fi
  if [ -n "${SERVER_PID:-}" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$REPO" "$LOG"
}
trap cleanup EXIT
DOCVAULT_REPO="$REPO" uv run uvicorn main:app --app-dir src --port "$PORT" >"$LOG" 2>&1 &
SERVER_PID=$!
SERVER_CHILD="$(pgrep -P "$SERVER_PID" 2>/dev/null || true)"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
    break
  fi
  sleep 1
done
if ! curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
  echo "server не поднялся" >&2
  cat "$LOG" >&2
  exit 1
fi
uv run --with schemathesis schemathesis run "http://127.0.0.1:$PORT/openapi.json" \
  --checks all --exclude-checks allow_header_conformance

echo "preflight OK"
