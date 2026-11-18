#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src"
export DOCVAULT_REPO="${DOCVAULT_REPO:-$ROOT/data/demo-agent}"
export DOCVAULT_CAPABILITY_SECRET="${DOCVAULT_CAPABILITY_SECRET:-dev-demo-secret}"
export DOCVAULT_BROKER_SOCKET="${DOCVAULT_BROKER_SOCKET:-$ROOT/data/broker.sock}"
export DOCVAULT_SPACE="${DOCVAULT_SPACE:-default}"
export DOCVAULT_IDEM_KEY="${DOCVAULT_IDEM_KEY:-demo-agent-write-1}"

mkdir -p "$(dirname "$DOCVAULT_BROKER_SOCKET")"
rm -rf "$DOCVAULT_REPO"
uv run python -m cli.dv --path "$DOCVAULT_REPO" init

export DOCVAULT_DRAFT_ID="$(uv run python -c "from pathlib import Path; from core.repo import Repository; repo=Repository.open(Path('$DOCVAULT_REPO')); d=repo.drafts.create('$DOCVAULT_SPACE','user:host', repo.pointers.head('$DOCVAULT_SPACE')); print(d['id']); repo.close()")"
echo "draft: $DOCVAULT_DRAFT_ID"

uv run python -m broker.main serve --socket "$DOCVAULT_BROKER_SOCKET" --repo "$DOCVAULT_REPO" &
BPID=$!
trap 'kill "$BPID" 2>/dev/null || true; rm -f "$DOCVAULT_BROKER_SOCKET"' EXIT
sleep 0.4

export DOCVAULT_CAPABILITY_TOKEN="$(
  uv run python -c "from core.capability.tokens import issue_token; print(issue_token(space='$DOCVAULT_SPACE', path_prefixes=['docs/'], ops=['write_doc','ping'], draft_id='$DOCVAULT_DRAFT_ID'))"
)"

TASK_PY="$(mktemp)"
uv run python -c "from agent.pipeline import run_pipeline; open('$TASK_PY','w').write(run_pipeline('update_tariffs'))"

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker build -f "$ROOT/docker/sandbox.Dockerfile" -t docvault-sandbox:local "$ROOT" >/dev/null
  docker run --rm --network none \
    -v "$DOCVAULT_BROKER_SOCKET:/run/broker.sock" \
    -v "$TASK_PY:/work/task.py:ro" \
    -v "$ROOT/src:/work/src:ro" \
    -e DOCVAULT_BROKER_SOCKET=/run/broker.sock \
    -e DOCVAULT_CAPABILITY_TOKEN \
    -e DOCVAULT_SPACE \
    -e DOCVAULT_IDEM_KEY \
    -e PYTHONPATH=/work/src \
    --user 1000:1000 \
    docvault-sandbox:local python /work/task.py
else
  export DOCVAULT_BROKER_SOCKET
  uv run python "$TASK_PY"
fi

rm -f "$TASK_PY"
uv run python -m cli.dv --path "$DOCVAULT_REPO" commit --draft "$DOCVAULT_DRAFT_ID" -m "agent demo"
echo "demo-agent OK"