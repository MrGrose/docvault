import io
import json
import urllib.error
import urllib.request

import pytest

from agent.llm import openrouter


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_complete_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(openrouter.LlmError, match="OPENROUTER_API_KEY"):
        openrouter.complete("hi")


def test_complete_returns_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    payload = {"choices": [{"message": {"content": "write_doc('a.md', 'x')"}}]}

    def fake_urlopen(_request: object, timeout: float = 0) -> _Response:
        return _Response(json.dumps(payload).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert openrouter.complete("hi") == "write_doc('a.md', 'x')"


def test_complete_maps_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    def fake_urlopen(_request: object, timeout: float = 0) -> _Response:
        raise urllib.error.HTTPError("url", 429, "rate", None, io.BytesIO(b'{"error":"limit"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(openrouter.LlmError, match="HTTP 429"):
        openrouter.complete("hi")


def test_complete_maps_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    def fake_urlopen(_request: object, timeout: float = 0) -> _Response:
        raise OSError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(openrouter.LlmError, match="недоступен"):
        openrouter.complete("hi")


def test_complete_rejects_unexpected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    def fake_urlopen(_request: object, timeout: float = 0) -> _Response:
        return _Response(b'{"id":"x"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(openrouter.LlmError, match="неожиданный ответ"):
        openrouter.complete("hi")
