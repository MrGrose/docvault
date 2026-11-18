from agent.extract import changed_paragraphs, paragraphs


def test_paragraphs_normalizes_newlines() -> None:
    assert paragraphs("a\r\n\r\nb\n\n\nc") == ["a", "b", "c"]


def test_changed_paragraphs_reports_insert_update_delete() -> None:
    old = "first\n\nsecond\n\nthird"
    new = "first\n\nsecond changed\n\nthird\n\nfourth"
    items = changed_paragraphs(old, new)
    kinds = [(item["change_kind"], item["text"]) for item in items]
    assert ("update", "second changed") in kinds
    assert ("add", "fourth") in kinds

    removed = changed_paragraphs(old, "first\n\nthird")
    assert ("delete", "second") in [(item["change_kind"], item["text"]) for item in removed]


def test_changed_paragraphs_truncates_long_text() -> None:
    items = changed_paragraphs("", "x" * 5000)
    assert len(items) == 1
    assert len(items[0]["text"]) == 4000
