from core.cdc.buzhash import chunk_bytes
from core.cdc.fixed import fixed_chunks

FIXTURE = (b"SECTION-A\n" * 500 + b"MIDDLE\n" + b"SECTION-B\n" * 500)[:12000]
INSERT_POS = 6000


def test_fixed_chunks_shift_more_boundaries_than_cdc() -> None:
    modified = FIXTURE[:INSERT_POS] + b"X" + FIXTURE[INSERT_POS:]
    fixed_before = fixed_chunks(FIXTURE, size=4096)
    fixed_after = fixed_chunks(modified, size=4096)
    cdc_before = chunk_bytes(FIXTURE)
    cdc_after = chunk_bytes(modified)

    def changed_count(before: list[bytes], after: list[bytes]) -> int:
        return sum(1 for i in range(min(len(before), len(after))) if before[i] != after[i]) + abs(
            len(before) - len(after)
        )

    assert changed_count(fixed_before, fixed_after) >= changed_count(cdc_before, cdc_after)
