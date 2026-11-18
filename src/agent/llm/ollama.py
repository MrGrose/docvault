import json
import os
import urllib.error
import urllib.parse
import urllib.request

from agent.llm.openrouter import LlmError

DEFAULT_MODEL = "llama3.2"
DEFAULT_URL = "http://127.0.0.1:11434/api/generate"


def complete(prompt: str, model: str | None = None, timeout: float = 120.0) -> str:
    chosen = model or os.environ.get("DOCVAULT_OLLAMA_MODEL", DEFAULT_MODEL)
    url = os.environ.get("DOCVAULT_OLLAMA_URL", DEFAULT_URL)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise LlmError("Ollama должен слушать localhost")
    body = {"model": chosen, "prompt": prompt, "stream": False}
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise LlmError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except OSError as exc:
        raise LlmError(f"Ollama недоступен: {exc}") from exc
    content = data.get("response")
    if not isinstance(content, str):
        raise LlmError("неожиданный ответ Ollama")
    return content
