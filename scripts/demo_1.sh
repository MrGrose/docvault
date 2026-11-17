#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="${ROOT}/.dev/tmp/demo-1"
rm -rf "$DEMO"
mkdir -p "$DEMO"

cd "$ROOT"
export PYTHONPATH=src

uv run python -m cli.dv --path "$DEMO" init
echo "content v1" >"$DEMO/file1.txt"
uv run python -m cli.dv --path "$DEMO" write docs/a.txt "$DEMO/file1.txt"
uv run python -m cli.dv --path "$DEMO" commit -m "first"

HEAD=$(uv run python -m cli.dv --path "$DEMO" log | head -1)
echo "head line: $HEAD"

echo "content v2" >"$DEMO/file1.txt"
uv run python -m cli.dv --path "$DEMO" write docs/a.txt "$DEMO/file1.txt"
uv run python -m cli.dv --path "$DEMO" commit -m "second" --expect-head genesis && exit 1 || true

uv run python -m cli.dv --path "$DEMO" diff
uv run python -m cli.dv --path "$DEMO" commit -m "second"
uv run python -m cli.dv --path "$DEMO" log
echo "demo-1 OK"