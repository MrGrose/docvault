import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_MODEL = "cohere/north-mini-code:free"
DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"


class LlmError(Exception):
    pass


def complete(prompt: str, model: str | None = None, timeout: float = 90.0) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise LlmError("OPENROUTER_API_KEY не задан")

    chosen = model or os.environ.get("DOCVAULT_LLM_MODEL", DEFAULT_MODEL)
    body = {
        "model": chosen,
        "messages": [{"role": "user", "content": prompt}],
    }
    url = os.environ.get("DOCVAULT_LLM_URL", DEFAULT_URL)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "openrouter.ai":
        raise LlmError("неверный адрес LLM")
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "docvault",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise LlmError(f"LLM HTTP {exc.code}: {detail}") from exc
    except OSError as exc:
        raise LlmError(f"LLM недоступен: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError("неожиданный ответ LLM") from exc
    return str(content)
