def fixed_chunks(data: bytes, size: int = 4096) -> list[bytes]:
    if not data:
        return []
    return [data[i : i + size] for i in range(0, len(data), size)]
