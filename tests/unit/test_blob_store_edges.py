import hashlib
import json
from pathlib import Path

import pytest

from core.keys import blob_key, chunk_key
from core.kv import LmdbKv
from core.storage.blob_store import BlobStore


def test_put_dedup_and_roundtrip(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = BlobStore(kv)
    data = b"hello docvault" * 1000

    first = store.put(data)
    second = store.put(data)

    assert first == second == hashlib.sha256(data).hexdigest()
    assert store.read(first) == data
    assert store.chunk_hashes(first)
    kv.close()


def test_read_missing_blob_and_missing_chunk(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = BlobStore(kv)

    with pytest.raises(KeyError, match="blob не найден"):
        store.read("0" * 64)
    with pytest.raises(KeyError, match="blob не найден"):
        store.chunk_hashes("0" * 64)

    manifest = json.dumps(["deadbeef"]).encode("utf-8")
    kv.put_new(blob_key("a" * 64), manifest)
    with pytest.raises(KeyError, match="chunk не найден"):
        store.read("a" * 64)
    kv.close()


def test_legacy_raw_blob_is_read_as_is(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = BlobStore(kv)
    raw = b"raw legacy payload"
    digest = hashlib.sha256(raw).hexdigest()
    kv.put_new(blob_key(digest), raw)

    assert store.read(digest) == raw
    assert store.chunk_hashes(digest) == [hashlib.sha256(raw).hexdigest()]

    assert store.put(raw) == digest
    assert kv.get(blob_key(digest)) == raw
    kv.close()


def test_chunk_layout_matches_manifest(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = BlobStore(kv)
    data = bytes(range(256)) * 200

    digest = store.put(data)
    hashes = store.chunk_hashes(digest)
    rebuilt = b"".join(kv.get(chunk_key(h)) or b"" for h in hashes)

    assert rebuilt == data
    kv.close()


def test_diff_between_versions(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = BlobStore(kv)
    base = b"A" * 20_000
    changed = base[:10_000] + b"B" * 500 + base[10_500:]

    hash_a = store.put(base)
    hash_b = store.put(changed)
    diff = store.diff(hash_a, hash_b)

    assert diff
    assert all("index" in item for item in diff)
    assert any(item["before"] != item["after"] for item in diff)
    kv.close()


def test_tree_roundtrip_and_diff(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = BlobStore(kv)

    tree_a = store.put_tree({"a.md": "h1", "b.md": "h2"})
    tree_b = store.put_tree({"b.md": "h3", "c.md": "h4"})

    assert store.read_tree(tree_a) == {"a.md": "h1", "b.md": "h2"}
    diff = {item["path"]: item for item in store.diff_trees(tree_a, tree_b)}

    assert diff["a.md"]["after"] is None
    assert diff["b.md"]["before"] == "h2"
    assert diff["b.md"]["after"] == "h3"
    assert diff["c.md"]["before"] is None

    with pytest.raises(KeyError, match="tree не найден"):
        store.read_tree("missing")
    kv.close()
