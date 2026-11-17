#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src"
export DOCVAULT_REPO="${DOCVAULT_REPO:-$ROOT/data/demo-hitol}"

uv run python -m cli.dv --path "$DOCVAULT_REPO" init
uv run python "$ROOT/scripts/hitol_demo_client.py"
echo "demo-hitol OK"