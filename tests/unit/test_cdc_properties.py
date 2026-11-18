import random

from core.cdc import chunk_bytes
from core.cdc.buzhash import AVG_CHUNK, MAX_CHUNK, MIN_CHUNK


def test_chunk_roundtrip_many_sizes() -> None:
    rnd = random.Random(42)
    sizes = [0, 1, 2, 47, 48, 1023, 2048, 8192, 33000, 100000]
    for size in sizes:
        data = bytes(rnd.randrange(256) for _ in range(size))
        chunks = chunk_bytes(data)
        assert b"".join(chunks) == data
        for chunk in chunks[:-1]:
            assert MIN_CHUNK <= len(chunk) <= MAX_CHUNK


def test_chunking_is_stable_across_runs() -> None:
    rnd = random.Random(7)
    data = bytes(rnd.randrange(256) for _ in range(50000))
    assert chunk_bytes(data) == chunk_bytes(data)


def test_average_chunk_size_is_near_target() -> None:
    rnd = random.Random(3)
    data = bytes(rnd.randrange(256) for _ in range(400000))
    chunks = chunk_bytes(data)
    average = sum(len(c) for c in chunks) / len(chunks)
    assert AVG_CHUNK * 0.4 <= average <= AVG_CHUNK * 2.5
