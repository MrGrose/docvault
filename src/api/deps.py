import os
from functools import lru_cache
from pathlib import Path

from core.idempotency import IdempotencyStore
from core.repo import Repository


@lru_cache
def get_repository() -> Repository:
    root = Path(os.environ.get("DOCVAULT_REPO", "data/repo"))
    if not (root / ".docvault").exists():
        return Repository.init(root)
    return Repository.open(root)


def get_idempotency() -> IdempotencyStore:
    return IdempotencyStore(get_repository().kv)
