import zlib

MIN_CHUNK = 2 * 1024
AVG_CHUNK = 8 * 1024
MAX_CHUNK = 64 * 1024
_MASK = AVG_CHUNK - 1
_MASK64 = (1 << 64) - 1


def _splitmix64(value: int) -> int:
    seed = (value + 0x9E3779B97F4A7C15) & _MASK64
    seed = ((seed ^ (seed >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    seed = ((seed ^ (seed >> 27)) * 0x94D049BB133111EB) & _MASK64
    return seed ^ (seed >> 31)


TABLE = tuple(_splitmix64(zlib.crc32(bytes([i]))) for i in range(256))


def chunk_bytes(data: bytes) -> list[bytes]:
    if len(data) <= MIN_CHUNK:
        return [data]

    chunks: list[bytes] = []
    start = 0
    total = len(data)

    while start < total:
        if total - start <= MIN_CHUNK:
            chunks.append(data[start:])
            break

        hard_end = min(start + MAX_CHUNK, total)
        cut = hard_end
        h = 0

        for i in range(start, hard_end):
            h = ((h << 1) + TABLE[data[i]]) & _MASK64
            if i - start + 1 >= MIN_CHUNK and (h & _MASK) == 0:
                cut = i + 1
                break

        chunks.append(data[start:cut])
        start = cut

    return chunks
