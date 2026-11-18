from core.keys import revoked_key
from core.kv import LmdbKv, WriteTxn


class RevocationStore:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def revoke(self, jti: str) -> None:
        def body(txn: WriteTxn) -> None:
            txn.put(revoked_key(jti), b"1")

        self._kv.run_write(body)

    def is_revoked(self, jti: str) -> bool:
        return self._kv.get(revoked_key(jti)) is not None
