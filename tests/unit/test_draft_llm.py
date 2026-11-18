import pytest

from agent.pipeline import run_draft_stage
from agent.stages.draft_llm import build_prompt, draft_with_llm, extract_code


def test_extract_code_from_fence() -> None:
    text = "вот код\n```python\nwrite_doc('a.md', 'x')\n```\nготово"
    assert extract_code(text) == "write_doc('a.md', 'x')"


def test_extract_code_without_fence() -> None:
    assert extract_code("  write_doc('a.md', 'x')  ") == "write_doc('a.md', 'x')"


def test_build_prompt_includes_source() -> None:
    prompt = build_prompt("update_tariffs", "Basic: 100 RUB")
    assert "update_tariffs" in prompt
    assert "Basic: 100 RUB" in prompt
    assert "write_doc" in prompt


def test_draft_with_llm_returns_code(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(prompt: str) -> str:
        assert "Basic: 100 RUB" in prompt
        return "```python\nwrite_doc('docs/tariffs.md', 'Basic: 100 RUB')\n```"

    code = draft_with_llm("update_tariffs", "Basic: 100 RUB", client=fake)
    assert code.startswith("write_doc(")


def test_draft_with_llm_rejects_answer_without_write() -> None:
    with pytest.raises(ValueError, match="write_doc"):
        draft_with_llm("update_tariffs", "src", client=lambda _prompt: "print('nope')", attempts=1)


def test_draft_with_llm_retries_after_rule_violation() -> None:
    answers = [
        "def write_doc(path, content):\n    open(path, 'w')\nwrite_doc('a.md', 'x')",
        "write_doc('a.md', 'x')",
    ]
    code = draft_with_llm("update_tariffs", "src", client=lambda _prompt: answers.pop(0))
    assert code == "write_doc('a.md', 'x')"


def test_draft_with_llm_fails_after_bad_attempts() -> None:
    bad = "import os\nwrite_doc('a.md', 'x')"
    with pytest.raises(ValueError, match="не выдала корректный код"):
        draft_with_llm("update_tariffs", "src", client=lambda _prompt: bad)


def test_pipeline_uses_template_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCVAULT_LLM", raising=False)
    code = run_draft_stage("update_tariffs")
    assert "SandboxSdkClient" in code


def test_pipeline_uses_llm_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_LLM", "openrouter")
    code = run_draft_stage(
        "update_tariffs",
        source="Basic: 100 RUB",
        client=lambda _prompt: "write_doc('docs/tariffs.md', 'Basic: 100 RUB')",
    )
    assert code == "write_doc('docs/tariffs.md', 'Basic: 100 RUB')"
