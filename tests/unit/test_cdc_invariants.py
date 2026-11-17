import hashlib
import os
from pathlib import Path

from core.cdc import AVG_CHUNK, MAX_CHUNK, MIN_CHUNK, chunk_bytes
from core.kv import LmdbKv
from core.storage.blob_store import BlobStore


def _assert_chunk_sizes(chunks: list[bytes]) -> None:
    for idx, c in enumerate(chunks):
        if idx < len(chunks) - 1:
            assert MIN_CHUNK <= len(c) <= MAX_CHUNK
        else:
            assert 0 < len(c) <= MAX_CHUNK


def test_chunk_roundtrip() -> None:
    data = (b"The quick brown fox jumps over the lazy dog.\n" * 400)[:33000]
    chunks = chunk_bytes(data)
    assert chunks
    assert b"".join(chunks) == data
    _assert_chunk_sizes(chunks)


def test_chunking_is_deterministic() -> None:
    data = b"x" * 25000 + b"needle" + b"y" * 25000
    assert chunk_bytes(data) == chunk_bytes(data)


def test_blob_store_roundtrip(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = BlobStore(kv)
    payload = bytes(range(256)) * 120
    blob_hash = store.put(payload)
    assert store.read(blob_hash) == payload
    assert hashlib.sha256(payload).hexdigest() == blob_hash
    kv.close()


def test_avg_chunk_size_sane() -> None:
    data = os.urandom(200_000)
    chunks = chunk_bytes(data)
    sizes = [len(c) for c in chunks]
    avg = sum(sizes) / len(sizes)
    assert avg < AVG_CHUNK * 2.5
    assert avg > AVG_CHUNK / 4
