import io
import json
import urllib.error
import urllib.request

import pytest

from agent.llm import ollama
from agent.pipeline import run_draft_stage


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_complete_reads_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_request: object, timeout: float = 0) -> _Response:
        return _Response(json.dumps({"response": "write_doc('docs/a.md', 'x')"}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert "write_doc" in ollama.complete("hi")


def test_complete_rejects_remote_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_OLLAMA_URL", "http://example.com/api/generate")
    with pytest.raises(ollama.LlmError, match="localhost"):
        ollama.complete("hi")


def test_complete_maps_http_and_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def http_error(_request: object, timeout: float = 0) -> _Response:
        raise urllib.error.HTTPError("url", 500, "boom", {}, io.BytesIO(b"detail"))

    monkeypatch.setattr(urllib.request, "urlopen", http_error)
    with pytest.raises(ollama.LlmError, match="HTTP 500"):
        ollama.complete("hi")

    def network_error(_request: object, timeout: float = 0) -> _Response:
        raise OSError("down")

    monkeypatch.setattr(urllib.request, "urlopen", network_error)
    with pytest.raises(ollama.LlmError, match="недоступен"):
        ollama.complete("hi")


def test_complete_rejects_missing_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_request: object, timeout: float = 0) -> _Response:
        return _Response(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ollama.LlmError, match="неожиданный"):
        ollama.complete("hi")


def test_pipeline_uses_ollama_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_LLM", "ollama")
    prompts: list[str] = []

    def fake_client(prompt: str) -> str:
        prompts.append(prompt)
        return "write_doc('docs/a.md', 'x')"

    code = run_draft_stage("update_tariffs", "source", client=fake_client)
    assert "write_doc" in code
    assert prompts
