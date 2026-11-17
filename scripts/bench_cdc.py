#!/usr/bin/env python3
import hashlib
import random
import time

from core.cdc.buzhash import chunk_bytes
from core.cdc.fixed import fixed_chunks


def _simulate_versions(size: int, versions: int, edit_ratio: float) -> list[bytes]:
    base = bytearray(random.randbytes(size))
    out = [bytes(base)]
    span = max(1, int(size * edit_ratio))
    for _ in range(versions - 1):
        data = bytearray(out[-1])
        pos = 0 if span >= len(data) else random.randint(0, len(data) - span)
        for i in range(pos, pos + span):
            data[i] = (data[i] + 17) % 256
        out.append(bytes(data))
    return out


def _dedup_ratio(chunks_per_version: list[list[bytes]]) -> float:
    unique: set[str] = set()
    total_chunks = 0
    for chunks in chunks_per_version:
        total_chunks += len(chunks)
        for c in chunks:
            unique.add(hashlib.sha256(c).hexdigest())
    if not unique:
        return 0.0
    return total_chunks / len(unique)


def main() -> None:
    random.seed(42)
    size = 300 * 1024
    versions = 10
    edit = 0.02
    docs = _simulate_versions(size, versions, edit)

    t0 = time.perf_counter()
    cdc_chunks = [chunk_bytes(d) for d in docs]
    cdc_dt = time.perf_counter() - t0

    t1 = time.perf_counter()
    fixed_chunks_list = [fixed_chunks(d, size=4096) for d in docs]
    fixed_dt = time.perf_counter() - t1

    cdc_ratio = _dedup_ratio(cdc_chunks)
    fixed_ratio = _dedup_ratio(fixed_chunks_list)

    print("CDC bench (10 x 300KB, contiguous 2% block edit per version)")
    print(f"  cdc chunking sec:     {cdc_dt:.3f}")
    print(f"  fixed chunking sec:   {fixed_dt:.3f}")
    print(f"  cdc dedup ratio:      {cdc_ratio:.2f}x")
    print(f"  fixed dedup ratio:    {fixed_ratio:.2f}x")
    print(f"  cdc chunks last ver:  {len(cdc_chunks[-1])}")
    print(f"  fixed chunks last:    {len(fixed_chunks_list[-1])}")


if __name__ == "__main__":
    main()
