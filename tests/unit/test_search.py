from pathlib import Path

from core.repo import Repository


def test_search_finds_published_text(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    blob = repo.blobs.put("Тариф Basic: 100 рублей".encode())
    count = repo.search.index_tree("default", {"docs/tariffs.md": blob})
    assert count == 1

    items = repo.search.search("тариф")
    assert len(items) == 1
    assert items[0]["path"] == "docs/tariffs.md"
    assert "[Тариф]" in items[0]["snippet"] or "Тариф" in items[0]["snippet"]
    assert repo.search.search("missing") == []
    assert repo.search.search("тариф", space="other") == []
    repo.close()


def test_search_upsert_and_clear(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    first = repo.blobs.put(b"old text")
    second = repo.blobs.put(b"new text")
    repo.search.index_tree("default", {"docs/a.md": first})
    repo.search.index_tree("default", {"docs/a.md": second})

    assert repo.search.count() == 1
    assert repo.search.search("new")
    assert repo.search.search("old") == []
    repo.search.clear()
    assert repo.search.count() == 0
    repo.close()


def test_rebuild_indexes_head_tree(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    draft = repo.drafts.create("default", "user:host", None)
    repo.write_draft(str(draft["id"]), "docs/a.md", "hello search")
    repo.publish_draft(str(draft["id"]), None, "add", "user:host")
    repo.search.clear()
    assert repo.search.count() == 0

    assert repo.rebuild_search() == 1
    assert repo.search.search("hello")
    repo.close()


def test_search_ignores_punctuation_and_control_characters(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    blob = repo.blobs.put(b"hello")
    repo.search.index_tree("default", {"docs/a.md": blob})
    assert repo.search.search("!!!") == []
    assert repo.search.search("\x00\x1f") == []
    repo.close()
