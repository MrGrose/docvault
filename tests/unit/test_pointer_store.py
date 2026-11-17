from pathlib import Path

import pytest

from core.errors import ConflictError
from core.kv import LmdbKv
from core.storage.pointer_store import PointerStore


def test_cas_head_success_then_conflict(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = PointerStore(kv)

    assert store.head("default") is None
    store.cas_head("default", b"cs1", expect=None)
    assert store.head("default") == b"cs1"

    with pytest.raises(ConflictError, match="head изменился"):
        store.cas_head("default", b"cs2", expect=b"stale")

    store.cas_head("default", b"cs3", expect=b"cs1")
    assert store.head("default") == b"cs3"
    kv.close()
