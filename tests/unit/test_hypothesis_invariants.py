import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from core.cdc import chunk_bytes
from core.kv import LmdbKv
from core.storage.blob_store import BlobStore


@given(st.binary(max_size=20000))
@settings(max_examples=40, deadline=None)
def test_chunk_roundtrip_for_arbitrary_bytes(data: bytes) -> None:
    assert b"".join(chunk_bytes(data)) == data


@given(st.binary(max_size=1000))
@settings(max_examples=30, deadline=None)
def test_cas_never_writes_with_wrong_expectation(data: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        kv = LmdbKv.open(Path(tmp) / "db")
        assert kv.put_cas(b"key", data, None) is True
        assert kv.put_cas(b"key", b"other", None) is False
        assert kv.get(b"key") == data
        kv.close()


@given(st.binary(max_size=10000))
@settings(max_examples=30, deadline=None)
def test_blob_put_is_content_addressed(data: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        kv = LmdbKv.open(Path(tmp) / "db")
        blobs = BlobStore(kv)
        first = blobs.put(data)
        second = blobs.put(data)
        assert first == second
        assert blobs.read(first) == data
        kv.close()
