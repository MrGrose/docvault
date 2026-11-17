from pathlib import Path

import pytest

from core.errors import ConflictError
from core.kv import LmdbKv


def test_put_cas_new_key_and_cas_cycle(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    assert kv.put_cas(b"head:main", b"cs1", expect=None) is True
    assert kv.put_cas(b"head:main", b"cs2", expect=b"cs1") is True
    assert kv.put_cas(b"head:main", b"cs3", expect=b"cs1") is False
    assert kv.get(b"head:main") == b"cs2"
    assert kv.put_cas(b"head:main", b"cs4", expect=None) is False
    kv.close()


def test_put_new_rejects_existing_key(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    kv.put_new(b"cs:one", b"payload")
    with pytest.raises(ConflictError, match="ключ уже существует"):
        kv.put_new(b"cs:one", b"other")
    kv.close()


def test_scan_returns_only_matching_prefix_in_order(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    for key in (b"blob:2", b"blob:1", b"tree:1", b"blob:3"):
        kv.put_new(key, key.upper())
    pairs = list(kv.scan(b"blob:"))
    assert [k for k, _ in pairs] == [b"blob:1", b"blob:2", b"blob:3"]
    assert list(kv.scan(b"nothing:")) == []
    kv.close()


def test_snapshot_isolation_and_idempotent_close(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    kv.put_cas(b"head:main", b"cs1", expect=None)
    snap = kv.snapshot()
    assert snap.get(b"head:main") == b"cs1"

    kv.put_cas(b"head:main", b"cs2", expect=b"cs1")

    assert snap.get(b"head:main") == b"cs1"
    assert list(snap.scan(b"head:")) == [(b"head:main", b"cs1")]
    snap.close()
    snap.close()
    kv.close()


def test_write_txn_delete_and_read_back(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    kv.put_new(b"idem:k", b"v")

    def drop(txn: object) -> None:
        assert hasattr(txn, "delete")
        txn.delete(b"idem:k")  # type: ignore[attr-defined]

    kv.run_write(drop)
    assert kv.get(b"idem:k") is None
    kv.close()


def test_compare_and_swap_head_two_failures(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    kv.put_new(b"head:main", b"cs1")

    with pytest.raises(ConflictError, match="head изменился"):
        kv.compare_and_swap_head(b"head:main", b"cs:new", b"{}", b"cs_new", expected_head=b"cs0")

    kv.put_new(b"cs:new", b"{}")
    with pytest.raises(ConflictError, match="changeset уже существует"):
        kv.compare_and_swap_head(b"head:main", b"cs:new", b"{}", b"cs_new", expected_head=b"cs1")

    kv.compare_and_swap_head(b"head:main", b"cs:next", b"{}", b"cs_next", expected_head=b"cs1")
    assert kv.get(b"head:main") == b"cs_next"
    kv.close()
