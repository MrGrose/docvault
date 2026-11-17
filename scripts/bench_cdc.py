#!/usr/bin/env python3
"""Benchmark CDC (buzhash) against fixed-size chunking on three edit patterns.

Both algorithms are compared by storage ratio: total bytes of all versions
divided by bytes actually stored after deduplication. Chunk-count ratios are
not comparable, because CDC and fixed chunking produce a different number of
chunks of different sizes.
"""

import hashlib
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.cdc.buzhash import chunk_bytes  # noqa: E402
from core.cdc.fixed import fixed_chunks  # noqa: E402

SIZE = 300 * 1024
VERSIONS = 10
FIXED_CHUNK = 4096
BLOCK = 3000
EDIT_RATIO = 0.02
SEED = 42


def _make_versions(base: bytes, mode: str) -> list[bytes]:
    rng = random.Random(SEED)
    out = [base]
    for _ in range(VERSIONS - 1):
        data = bytearray(out[-1])
        if mode == "insert":
            pos = rng.randint(0, len(data))
            data[pos:pos] = bytes(rng.randrange(256) for _ in range(BLOCK))
        elif mode == "delete":
            if len(data) > BLOCK * 2:
                pos = rng.randint(0, len(data) - BLOCK)
                del data[pos : pos + BLOCK]
        else:
            span = max(1, int(len(data) * EDIT_RATIO))
            pos = rng.randint(0, len(data) - span)
            for i in range(pos, pos + span):
                data[i] = (data[i] + 17) % 256
        out.append(bytes(data))
    return out


def _measure(chunks_per_version: list[list[bytes]]) -> tuple[float, int, int]:
    total = 0
    unique: dict[bytes, int] = {}
    for chunks in chunks_per_version:
        for chunk in chunks:
            total += len(chunk)
            unique.setdefault(hashlib.sha256(chunk).digest(), len(chunk))
    stored = sum(unique.values())
    ratio = total / stored if stored else 0.0
    return ratio, stored, len(unique)


def _run_case(name: str, docs: list[bytes]) -> None:
    t0 = time.perf_counter()
    cdc_chunks = [chunk_bytes(d) for d in docs]
    cdc_dt = time.perf_counter() - t0

    t1 = time.perf_counter()
    fixed_list = [fixed_chunks(d, size=FIXED_CHUNK) for d in docs]
    fixed_dt = time.perf_counter() - t1

    cdc_ratio, cdc_stored, cdc_unique = _measure(cdc_chunks)
    fixed_ratio, fixed_stored, fixed_unique = _measure(fixed_list)

    print(f"{name}: {VERSIONS} versions, base {SIZE // 1024} KB, last {len(docs[-1]) // 1024} KB")
    print(
        f"  cdc   {cdc_ratio:5.2f}x  stored {cdc_stored // 1024:4d} KB"
        f"  unique {cdc_unique:3d}  chunks(last) {len(cdc_chunks[-1]):3d}  time {cdc_dt:.3f}s"
    )
    print(
        f"  fixed {fixed_ratio:5.2f}x  stored {fixed_stored // 1024:4d} KB"
        f"  unique {fixed_unique:3d}  chunks(last) {len(fixed_list[-1]):3d}  time {fixed_dt:.3f}s"
    )
    print()


def main() -> None:
    rng = random.Random(SEED)
    base = bytes(rng.randrange(256) for _ in range(SIZE))
    print(f"CDC bench, fixed chunk {FIXED_CHUNK} B, edit block {BLOCK} B, seed {SEED}")
    print()
    _run_case("in-place edit 2%", _make_versions(base, "in-place"))
    _run_case("insert 3000 B", _make_versions(base, "insert"))
    _run_case("delete 3000 B", _make_versions(base, "delete"))


if __name__ == "__main__":
    main()
