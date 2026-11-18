from pathlib import Path

from core.kv import LmdbKv
from core.repo import Repository


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
