import json
import uuid
from dataclasses import dataclass
from typing import Any

from core.errors import ConflictError
from core.keys import cs_key, head_key
from core.kv import LmdbKv, WriteTxn
from core.storage.blob_store import BlobStore
from core.storage.pointer_store import PointerStore
from core.storage.working_copy import WorkingCopy


@dataclass
class ConflictInfo:
    space: str
    expected_head: str | None
    actual_head: str | None
    message: str


class ChangesetStore:
    def __init__(
        self,
        kv: LmdbKv,
        pointers: PointerStore,
        blobs: BlobStore,
        work: WorkingCopy,
    ) -> None:
        self._kv = kv
        self._pointers = pointers
        self._blobs = blobs
        self._work = work

    def commit_working_copy(
        self,
        space: str,
        message: str,
        author: str,
        expected_head: bytes | None,
    ) -> str:
        paths = self._work.read(space)
        if not paths:
            raise ValueError("нет изменений для коммита")

        tree_hash = self._blobs.put_tree(paths)
        parent_raw = self._pointers.head(space)
        parent_id = parent_raw.decode() if parent_raw else None

        cs_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "id": cs_id,
            "space": space,
            "parent": parent_id,
            "tree_hash": tree_hash,
            "author": author,
            "message": message,
            "provenance": [],
            "status": "published",
        }
        body = json.dumps(record, ensure_ascii=False).encode("utf-8")
        try:
            self._kv.compare_and_swap_head(
                head_key(space),
                cs_key(cs_id),
                body,
                cs_id.encode(),
                expected_head=expected_head,
            )
        except ConflictError as exc:
            actual = self._pointers.head(space)
            raise ConflictError(
                f"{exc}; actual_head={actual.decode() if actual else None}"
            ) from exc

        self._work.clear(space)
        return cs_id

    def commit_working_copy_in_txn(
        self,
        txn: WriteTxn,
        space: str,
        message: str,
        author: str,
        expected_head: bytes | None,
    ) -> str:
        paths = self._work.read_in_txn(txn, space)
        if not paths:
            raise ValueError("нет изменений для коммита")

        tree_hash = self._blobs.put_tree_in_txn(txn, paths)
        parent_raw = txn.get(head_key(space))
        parent_id = parent_raw.decode() if parent_raw else None

        cs_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "id": cs_id,
            "space": space,
            "parent": parent_id,
            "tree_hash": tree_hash,
            "author": author,
            "message": message,
            "provenance": [],
            "status": "published",
        }
        body = json.dumps(record, ensure_ascii=False).encode("utf-8")
        try:
            txn.compare_and_swap_head(
                head_key(space),
                cs_key(cs_id),
                body,
                cs_id.encode(),
                expected_head=expected_head,
            )
        except ConflictError as exc:
            actual = txn.get(head_key(space))
            raise ConflictError(
                f"{exc}; actual_head={actual.decode() if actual else None}"
            ) from exc

        self._work.clear_in_txn(txn, space)
        return cs_id

    def get(self, cs_id: str) -> dict[str, Any]:
        raw = self._kv.get(cs_key(cs_id))
        if raw is None:
            msg = f"changeset не найден: {cs_id}"
            raise KeyError(msg)
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
        return data

    def log(self, space: str) -> list[dict[str, Any]]:
        head = self._pointers.head(space)
        if head is None:
            return []
        chain: list[dict[str, Any]] = []
        current_id = head.decode()
        while current_id:
            cs = self.get(current_id)
            chain.append(cs)
            parent = cs.get("parent")
            current_id = str(parent) if parent else ""
        return chain

    def rebase_hint(self, space: str, expected: bytes | None) -> ConflictInfo:
        actual = self._pointers.head(space)
        if actual == expected:
            return ConflictInfo(space, None, None, "head совпадает")
        return ConflictInfo(
            space=space,
            expected_head=expected.decode() if expected else None,
            actual_head=actual.decode() if actual else None,
            message="нужен rebase: перечитайте head и повторите commit",
        )
