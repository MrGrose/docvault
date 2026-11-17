from pathlib import Path
from typing import cast

from core.kv import LmdbKv
from core.repo import Repository

_HEAD_UNSET = object()


def parse_expect_head(value: str | None) -> bytes | None | object:
    """CLI: None -> current head; 'genesis' -> пустой head; иначе cs id bytes."""
    if value is None:
        return _HEAD_UNSET
    if value == "genesis":
        return None
    return value.encode()


def commit_changeset(
    store: Repository,
    space: str,
    message: str,
    author: str,
    expected_head: bytes | None | object = _HEAD_UNSET,
) -> str:
    if expected_head is _HEAD_UNSET:
        head_ref: bytes | None = store.pointers.head(space)
    else:
        head_ref = cast(bytes | None, expected_head)
    return store.changesets.commit_working_copy(
        space,
        message,
        author,
        head_ref,
    )


def read_head(store: Repository, space: str) -> bytes | None:
    return store.pointers.head(space)


class Store:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo
        self.root = repo.root

    @classmethod
    def open(cls, repo_path: Path) -> "Store":
        repo_path.mkdir(parents=True, exist_ok=True)
        if (repo_path / ".docvault").exists():
            repo = Repository.open(repo_path)
        else:
            kv = LmdbKv.open(repo_path / "lmdb")
            repo = Repository(repo_path, kv)
        return cls(repo)

    def init_repo(self) -> None:
        marker = self.root / ".docvault"
        if not marker.exists():
            marker.write_text("docvault\n", encoding="utf-8")

    def close(self) -> None:
        self._repo.close()

    @property
    def repo(self) -> Repository:
        return self._repo
