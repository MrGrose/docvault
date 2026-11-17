from pathlib import Path

from core.kv import LmdbKv


def test_snapshot_isolation(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "lmdb")
    kv.put_new(b"k1", b"v1")
    snap = kv.snapshot()
    try:
        assert snap.get(b"k1") == b"v1"
        kv.put_new(b"k2", b"v2")
        assert snap.get(b"k2") is None
    finally:
        snap.close()
    assert kv.get(b"k2") == b"v2"
    kv.close()
