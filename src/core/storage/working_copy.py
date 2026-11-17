import json

from core.keys import work_key
from core.kv import LmdbKv, WriteTxn


class WorkingCopy:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def read(self, space: str) -> dict[str, str]:
        raw = self._kv.get(work_key(space))
        if raw is None:
            return {}
        data: dict[str, str] = json.loads(raw.decode("utf-8"))
        return data

    def read_in_txn(self, txn: WriteTxn, space: str) -> dict[str, str]:
        raw = txn.get(work_key(space))
        if raw is None:
            return {}
        data: dict[str, str] = json.loads(raw.decode("utf-8"))
        return data

    def write(self, space: str, paths: dict[str, str]) -> None:
        body = json.dumps(paths, sort_keys=True, ensure_ascii=False).encode("utf-8")
        key = work_key(space)

        def save(txn: WriteTxn) -> None:
            txn.put(key, body)

        self._kv.run_write(save)

    def write_in_txn(self, txn: WriteTxn, space: str, paths: dict[str, str]) -> None:
        body = json.dumps(paths, sort_keys=True, ensure_ascii=False).encode("utf-8")
        txn.put(work_key(space), body)

    def set_path(self, space: str, path: str, blob_hash: str) -> None:
        paths = self.read(space)
        paths[path] = blob_hash
        self.write(space, paths)

    def set_path_in_txn(self, txn: WriteTxn, space: str, path: str, blob_hash: str) -> None:
        paths = self.read_in_txn(txn, space)
        paths[path] = blob_hash
        self.write_in_txn(txn, space, paths)

    def clear(self, space: str) -> None:
        key = work_key(space)
        if self._kv.get(key) is None:
            return

        def drop(txn: WriteTxn) -> None:
            if txn.get(key) is not None:
                txn.delete(key)

        self._kv.run_write(drop)

    def clear_in_txn(self, txn: WriteTxn, space: str) -> None:
        key = work_key(space)
        if txn.get(key) is not None:
            txn.delete(key)
