from pathlib import Path
from typing import Any

import pytest

from core.errors import AuthzError, ConflictError
from core.keys import DEFAULT_SPACE
from core.repo import Repository
from core.storage.draft_store import draft_content_hash


def _draft_with_file(repo: Repository, path: str, content: bytes) -> dict[str, Any]:
    draft = repo.drafts.create(DEFAULT_SPACE, "user:host", repo.pointers.head(DEFAULT_SPACE))
    blob = repo.blobs.put(content)
    repo.kv.run_write(
        lambda txn: repo.drafts.put_path_in_txn(txn, str(draft["id"]), path, blob, "user:host")
    )
    return repo.drafts.get(str(draft["id"]))


def test_draft_stores_paths_and_owner(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        draft = _draft_with_file(repo, "docs/a.md", b"hello")
        loaded = repo.drafts.get(str(draft["id"]))
        assert loaded["paths"]["docs/a.md"]
        assert loaded["owner"] == "user:host"
        assert loaded["status"] == "open"
        assert loaded["base_head"] is None
    finally:
        repo.close()


def test_write_rejects_other_owner(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        draft = repo.drafts.create(DEFAULT_SPACE, "user:host", None)
        blob = repo.blobs.put(b"x")
        with pytest.raises(AuthzError):
            repo.kv.run_write(
                lambda txn: repo.drafts.put_path_in_txn(
                    txn, str(draft["id"]), "docs/a.md", blob, "user:other"
                )
            )
    finally:
        repo.close()


def test_publish_moves_head_and_closes_draft(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        draft = _draft_with_file(repo, "docs/a.md", b"hello")
        cs_id = repo.publish_draft(str(draft["id"]), None, "first", "user:host")
        assert repo.pointers.head(DEFAULT_SPACE) == cs_id.encode()
        assert repo.drafts.get(str(draft["id"]))["status"] == "published"
        cs = repo.changesets.get(cs_id)
        assert cs["draft_id"] == draft["id"]
        assert cs["base_head"] is None
    finally:
        repo.close()


def test_publish_requires_matching_base_head(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        draft = _draft_with_file(repo, "docs/a.md", b"hello")
        with pytest.raises(ConflictError, match="base_head"):
            repo.publish_draft(str(draft["id"]), b"deadbeef", "first", "user:host")
        assert repo.pointers.head(DEFAULT_SPACE) is None
    finally:
        repo.close()


def test_publish_closed_draft_is_rejected(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        draft = _draft_with_file(repo, "docs/a.md", b"hello")
        repo.publish_draft(str(draft["id"]), None, "first", "user:host")
        with pytest.raises(ConflictError, match="не открыт"):
            repo.publish_draft(str(draft["id"]), None, "again", "user:host")
    finally:
        repo.close()


def test_rebase_creates_new_draft_and_marks_conflict(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        seed = _draft_with_file(repo, "docs/a.md", b"v1")
        base = repo.publish_draft(str(seed["id"]), None, "seed", "user:host")

        first = _draft_with_file(repo, "docs/a.md", b"first edit")
        second = _draft_with_file(repo, "docs/a.md", b"second edit")
        repo.publish_draft(str(second["id"]), base.encode(), "second", "user:other")

        rebased = repo.rebase_draft(str(first["id"]))
        assert rebased["id"] != first["id"]
        assert rebased["parent_draft"] == first["id"]
        assert rebased["conflicts"] == ["docs/a.md"]
        assert repo.drafts.get(str(first["id"]))["status"] == "open"
        assert repo.drafts.get(str(first["id"]))["paths"] == first["paths"]
    finally:
        repo.close()


def test_rebase_keeps_clean_paths(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        seed = _draft_with_file(repo, "docs/a.md", b"v1")
        base = repo.publish_draft(str(seed["id"]), None, "seed", "user:host")

        mine = _draft_with_file(repo, "docs/mine.md", b"mine")
        other = _draft_with_file(repo, "docs/other.md", b"other")
        repo.publish_draft(str(other["id"]), base.encode(), "other", "user:other")

        rebased = repo.rebase_draft(str(mine["id"]))
        assert rebased["conflicts"] == []
        assert rebased["paths"]["docs/mine.md"] == mine["paths"]["docs/mine.md"]
    finally:
        repo.close()


def test_missing_draft_raises_key_error(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        with pytest.raises(KeyError, match="draft не найден"):
            repo.drafts.get("missing")
    finally:
        repo.close()


def test_write_to_closed_draft_is_rejected(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        draft = _draft_with_file(repo, "docs/a.md", b"hello")
        repo.publish_draft(str(draft["id"]), None, "first", "user:host")
        blob = repo.blobs.put(b"again")
        with pytest.raises(ConflictError, match="не открыт"):
            repo.kv.run_write(
                lambda txn: repo.drafts.put_path_in_txn(
                    txn, str(draft["id"]), "docs/a.md", blob, "user:host"
                )
            )
    finally:
        repo.close()


def test_rebase_closed_draft_is_rejected(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        draft = _draft_with_file(repo, "docs/a.md", b"hello")
        repo.publish_draft(str(draft["id"]), None, "first", "user:host")
        with pytest.raises(ConflictError, match="не открыт"):
            repo.rebase_draft(str(draft["id"]))
    finally:
        repo.close()


def test_content_hash_changes_with_paths_and_base(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    first = repo.drafts.create("default", "user:host", None, paths={"docs/a.md": "1"})
    second = repo.drafts.create("default", "user:host", None, paths={"docs/a.md": "1"})
    third = repo.drafts.create("default", "user:host", None, paths={"docs/a.md": "2"})
    assert draft_content_hash(first) == draft_content_hash(second)
    assert draft_content_hash(first) != draft_content_hash(third)
    repo.close()
