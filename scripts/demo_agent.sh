#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec uv run --project "$ROOT" python "$ROOT/scripts/demo_agent.py"
