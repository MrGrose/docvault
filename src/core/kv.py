import os
from collections.abc import Callable, Iterator
from pathlib import Path
from types import TracebackType
from typing import ClassVar, TypeVar

import lmdb

from core.errors import ConflictError, StorageFullError

MAP_SIZE = 50 * 1024 * 1024

def map_size() -> int:
    return int(os.environ.get("DOCVAULT_MAP_SIZE", str(MAP_SIZE)))
T = TypeVar("T")


def _as_bytes(value: object | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytes):
        return value
    msg = f"ожидались bytes, получено {type(value)}"
    raise TypeError(msg)


class ReadTxn:
    def __init__(self, txn: lmdb.Transaction) -> None:
        self._txn = txn
        self._closed = False

    def get(self, key: bytes) -> bytes | None:
        return _as_bytes(self._txn.get(key))

    def scan(self, prefix: bytes) -> Iterator[tuple[bytes, bytes]]:
        cursor = self._txn.cursor()
        if not cursor.set_range(prefix):
            return
        for key, value in cursor:
            key_b = _as_bytes(key)
            if key_b is None or not key_b.startswith(prefix):
                break
            val_b = _as_bytes(value)
            if val_b is not None:
                yield key_b, val_b

    def close(self) -> None:
        if not self._closed:
            self._txn.abort()
            self._closed = True

    def __enter__(self) -> "ReadTxn":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class WriteTxn:
    def __init__(self, txn: lmdb.Transaction, db: lmdb._Database) -> None:
        self._txn = txn
        self._db = db

    def get(self, key: bytes) -> bytes | None:
        return _as_bytes(self._txn.get(key, db=self._db))

    def put(self, key: bytes, value: bytes) -> None:
        self._txn.put(key, value, db=self._db)

    def delete(self, key: bytes) -> None:
        self._txn.delete(key, db=self._db)

    def put_new(self, key: bytes, value: bytes) -> None:
        if self.get(key) is not None:
            raise ConflictError("ключ уже существует")
        self.put(key, value)

    def put_cas(self, key: bytes, value: bytes, expect: bytes | None = None) -> bool:
        current = self.get(key)
        if current != expect:
            return False
        self.put(key, value)
        return True

    def compare_and_swap_head(
        self,
        head_key: bytes,
        cs_key: bytes,
        cs_value: bytes,
        new_head: bytes,
        expected_head: bytes | None = None,
    ) -> None:
        current = self.get(head_key)
        if current != expected_head:
            raise ConflictError("head изменился")
        if self.get(cs_key) is not None:
            raise ConflictError("changeset уже существует")
        self.put(cs_key, cs_value)
        self.put(head_key, new_head)


class LmdbKv:
    _opened: ClassVar[dict[str, tuple[lmdb.Environment, lmdb._Database]]] = {}

    def __init__(self, env: lmdb.Environment, db: lmdb._Database) -> None:
        self._env = env
        self._db = db

    @classmethod
    def open(cls, data_dir: Path) -> "LmdbKv":
        data_dir.mkdir(parents=True, exist_ok=True)
        cache_key = str(data_dir.resolve())
        cached = cls._opened.get(cache_key)
        if cached is not None:
            env, db = cached
            return cls(env, db)
        try:
            env = lmdb.open(
                str(data_dir),
                map_size=map_size(),
                max_dbs=1,
                subdir=True,
            )
            db = env.open_db(b"kv")
        except lmdb.MapFullError as exc:
            raise StorageFullError(
                "LMDB map size исчерпан, увеличьте DOCVAULT_MAP_SIZE"
            ) from exc
        cls._opened[cache_key] = (env, db)
        return cls(env, db)

    @property
    def env(self) -> lmdb.Environment:
        return self._env

    @property
    def db(self) -> lmdb._Database:
        return self._db

    def run_write(self, fn: Callable[[WriteTxn], T]) -> T:
        try:
            with self._env.begin(db=self._db, write=True) as txn:
                return fn(WriteTxn(txn, self._db))
        except lmdb.MapFullError as exc:
            raise StorageFullError(
                "LMDB map size исчерпан, увеличьте DOCVAULT_MAP_SIZE"
            ) from exc

    def get(self, key: bytes) -> bytes | None:
        with self._env.begin(db=self._db) as txn:
            return _as_bytes(txn.get(key))

    def put_cas(self, key: bytes, value: bytes, expect: bytes | None = None) -> bool:
        def body(w: WriteTxn) -> bool:
            return w.put_cas(key, value, expect=expect)

        return self.run_write(body)

    def put_new(self, key: bytes, value: bytes) -> None:
        def body(w: WriteTxn) -> None:
            w.put_new(key, value)

        self.run_write(body)

    def scan(self, prefix: bytes) -> Iterator[tuple[bytes, bytes]]:
        with self._env.begin(db=self._db) as txn:
            cursor = txn.cursor()
            if not cursor.set_range(prefix):
                return
            for key, value in cursor:
                key_b = _as_bytes(key)
                if key_b is None or not key_b.startswith(prefix):
                    break
                val_b = _as_bytes(value)
                if val_b is not None:
                    yield key_b, val_b

    def snapshot(self) -> ReadTxn:
        return ReadTxn(self._env.begin(db=self._db))

    def compare_and_swap_head(
        self,
        head_key: bytes,
        cs_key: bytes,
        cs_value: bytes,
        new_head: bytes,
        expected_head: bytes | None = None,
    ) -> None:
        def body(w: WriteTxn) -> None:
            w.compare_and_swap_head(
                head_key,
                cs_key,
                cs_value,
                new_head,
                expected_head=expected_head,
            )

        self.run_write(body)

    def close(self) -> None:
        return
