from pathlib import Path

import pytest

from core.errors import ConflictError
from core.keys import DEFAULT_SPACE
from core.store import Store, commit_changeset, read_head


def test_commit_changeset_updates_head(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    store = Store.open(repo_path)
    store.init_repo()
    blob = store.repo.blobs.put(b"hello")
    store.repo.work.set_path(DEFAULT_SPACE, "a.txt", blob)
    cs_id = commit_changeset(store.repo, DEFAULT_SPACE, message="first", author="test")
    assert read_head(store.repo, DEFAULT_SPACE) == cs_id.encode()
    store.close()


def test_commit_changeset_conflict_on_stale_head(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    store = Store.open(repo_path)
    store.init_repo()
    seen = read_head(store.repo, DEFAULT_SPACE)
    blob = store.repo.blobs.put(b"v1")
    store.repo.work.set_path(DEFAULT_SPACE, "a.txt", blob)
    commit_changeset(store.repo, DEFAULT_SPACE, message="one", author="a", expected_head=seen)
    blob2 = store.repo.blobs.put(b"v2")
    store.repo.work.set_path(DEFAULT_SPACE, "a.txt", blob2)
    with pytest.raises(ConflictError):
        commit_changeset(
            store.repo,
            DEFAULT_SPACE,
            message="two",
            author="b",
            expected_head=seen,
        )
    store.close()
