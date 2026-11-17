.PHONY: dev test lint test-fault demo-1 demo-agent demo-hitol

dev:
	uv run uvicorn main:app --app-dir src --reload --port 8080

test:
	uv run pytest

lint:
	uv run ruff check . && uv run mypy src

demo-1:
	./scripts/demo_1.sh

demo-agent:
	chmod +x scripts/demo_agent.sh
	./scripts/demo_agent.sh

demo-hitol:
	chmod +x scripts/demo_hitol.sh
	./scripts/demo_hitol.sh
	
test-fault:
	RUN_FAULT_TESTS=1 uv run pytest tests/fault/ -v
