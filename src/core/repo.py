from pathlib import Path

from core.keys import DEFAULT_OWNER, DEFAULT_SPACE
from core.kv import LmdbKv
from core.storage import BlobStore, ChangesetStore, PointerStore, WorkingCopy


class Repository:
    def __init__(self, root: Path, kv: LmdbKv) -> None:
        self.root = root
        self.kv = kv
        self.pointers = PointerStore(kv)
        self.blobs = BlobStore(kv)
        self.work = WorkingCopy(kv)
        self.changesets = ChangesetStore(kv, self.pointers, self.blobs, self.work)

    @classmethod
    def open(cls, repo_path: Path) -> "Repository":
        repo_path.mkdir(parents=True, exist_ok=True)
        marker = repo_path / ".docvault"
        if not marker.exists():
            raise FileNotFoundError("репозиторий не инициализирован — сначала dv init")
        kv = LmdbKv.open(repo_path / "lmdb")
        return cls(repo_path, kv)

    @classmethod
    def init(cls, repo_path: Path) -> "Repository":
        repo_path.mkdir(parents=True, exist_ok=True)
        marker = repo_path / ".docvault"
        marker.write_text("docvault\n", encoding="utf-8")
        kv = LmdbKv.open(repo_path / "lmdb")
        return cls(repo_path, kv)

    def close(self) -> None:
        self.kv.close()

    @staticmethod
    def default_space() -> str:
        return DEFAULT_SPACE

    @staticmethod
    def default_owner() -> str:
        return DEFAULT_OWNER
