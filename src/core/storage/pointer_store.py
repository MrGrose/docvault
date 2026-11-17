from core.errors import ConflictError
from core.keys import head_key
from core.kv import LmdbKv


class PointerStore:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def head(self, space: str) -> bytes | None:
        return self._kv.get(head_key(space))

    def cas_head(self, space: str, new_id: bytes, expect: bytes | None = None) -> None:
        if not self._kv.put_cas(head_key(space), new_id, expect=expect):
            raise ConflictError("head изменился")
