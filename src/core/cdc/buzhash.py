import zlib

TABLE = [zlib.crc32(bytes([i])) & 0xFFFFFFFF for i in range(256)]

WINDOW_SIZE = 48
MIN_CHUNK = 2 * 1024
AVG_CHUNK = 8 * 1024
MAX_CHUNK = 64 * 1024
_MASK = AVG_CHUNK - 1


def _window_hash(data: bytes, end: int) -> int:
    h = 0
    for b in data[end - WINDOW_SIZE : end]:
        h = ((h << 1) ^ TABLE[b]) & 0xFFFFFFFF
    return h


def _roll(h: int, remove: int, add: int) -> int:
    h = (h ^ TABLE[remove]) & 0xFFFFFFFF
    h = ((h << 1) | (h >> 31)) & 0xFFFFFFFF
    return (h ^ TABLE[add]) & 0xFFFFFFFF


def chunk_bytes(data: bytes) -> list[bytes]:
    if len(data) <= MIN_CHUNK:
        return [data]

    chunks: list[bytes] = []
    start = 0
    while start < len(data):
        remaining = len(data) - start
        if remaining <= MIN_CHUNK:
            chunks.append(data[start:])
            break

        hard_end = min(start + MAX_CHUNK, len(data))
        i = start + MIN_CHUNK
        h = _window_hash(data, i) if i >= WINDOW_SIZE else 0

        cut = hard_end
        while i < hard_end:
            if i >= WINDOW_SIZE:
                h = _roll(h, data[i - WINDOW_SIZE], data[i - 1])
            if (h & _MASK) == 0:
                cut = i + 1
                break
            i += 1

        if cut <= start:
            cut = hard_end
        chunks.append(data[start:cut])
        start = cut

    return chunks
