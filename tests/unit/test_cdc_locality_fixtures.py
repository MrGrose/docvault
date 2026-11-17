import hashlib
import random

from core.cdc.buzhash import chunk_bytes

random.seed(7)
FIXTURE = bytes(random.randrange(256) for _ in range(96_000))
INSERT_POS = 4_300
# Вставка одного байта сдвигает границы только в окрестности правки,
# поэтому меняться должен один чанк (допускаем два на границе min/max).
MAX_CHANGED_CHUNKS = 2


def _chunk_digests(data: bytes) -> list[str]:
    return [hashlib.sha256(c).hexdigest() for c in chunk_bytes(data)]


def test_one_byte_insert_locality_regression() -> None:
    before = _chunk_digests(FIXTURE)
    modified = FIXTURE[:INSERT_POS] + b"Z" + FIXTURE[INSERT_POS:]
    after = _chunk_digests(modified)
    changed = sum(1 for a, b in zip(before, after, strict=False) if a != b)
    if len(before) != len(after):
        changed += abs(len(before) - len(after))
    assert changed <= MAX_CHANGED_CHUNKS
