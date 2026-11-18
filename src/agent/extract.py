import difflib
from typing import Any


def paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [part.strip() for part in normalized.split("\n\n") if part.strip()]


def changed_paragraphs(old: str, new: str) -> list[dict[str, Any]]:
    before = paragraphs(old)
    after = paragraphs(new)
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    items: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "insert"):
            kind = "add" if tag == "insert" else "update"
            for text in after[j1:j2]:
                items.append({"change_kind": kind, "text": text[:4000]})
        elif tag == "delete":
            for text in before[i1:i2]:
                items.append({"change_kind": "delete", "text": text[:4000]})
    return items
