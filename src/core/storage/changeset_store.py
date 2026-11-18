import json
import uuid
from dataclasses import dataclass
from typing import Any

from core.audit.log import append_in_txn
from core.errors import ConflictError, RebaseRequiredError
from core.keys import cs_key, head_key
from core.kv import LmdbKv, WriteTxn
from core.storage.blob_store import BlobStore
from core.storage.draft_store import DraftStore
from core.storage.pointer_store import PointerStore


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
        drafts: DraftStore,
    ) -> None:
        self._kv = kv
        self._pointers = pointers
        self._blobs = blobs
        self._drafts = drafts

    def publish_draft(
        self,
        draft_id: str,
        expected_head: bytes | None,
        message: str,
        author: str,
        approver: str | None = None,
        run_id: str | None = None,
        provenance: list[dict[str, Any]] | None = None,
        source: str = "api",
    ) -> str:
        result: dict[str, str] = {}

        def body(txn: WriteTxn) -> None:
            result["cs_id"] = self.publish_draft_in_txn(
                txn,
                draft_id,
                expected_head=expected_head,
                message=message,
                author=author,
                approver=approver,
                run_id=run_id,
                provenance=provenance,
                source=source,
            )

        self._kv.run_write(body)
        return result["cs_id"]

    def publish_draft_in_txn(
        self,
        txn: WriteTxn,
        draft_id: str,
        expected_head: bytes | None,
        message: str,
        author: str,
        approver: str | None = None,
        run_id: str | None = None,
        provenance: list[dict[str, Any]] | None = None,
        source: str = "api",
    ) -> str:
        draft = self._drafts.get_in_txn(txn, draft_id)
        if draft.get("status") != "open":
            raise ConflictError(f"draft не открыт: {draft.get('status')}")
        paths = dict(draft.get("paths") or {})
        if not paths:
            raise ValueError("нет изменений для коммита")

        base_head = draft.get("base_head")
        base_bytes = base_head.encode() if base_head else None
        if expected_head != base_bytes:
            actual = txn.get(head_key(str(draft["space"])))
            raise ConflictError(
                "expected_head не совпадает с base_head draft; "
                f"base_head={base_head} actual_head={actual.decode() if actual else None}"
            )

        space = str(draft["space"])
        base_tree: dict[str, str] = {}
        if base_head:
            raw = txn.get(cs_key(base_head))
            if raw is not None:
                base_record = json.loads(raw.decode("utf-8"))
                base_tree = self._blobs.read_tree(str(base_record["tree_hash"]))
        merged = dict(base_tree)
        merged.update(paths)
        tree_hash = self._blobs.put_tree_in_txn(txn, merged)
        parent_raw = txn.get(head_key(space))
        parent_id = parent_raw.decode() if parent_raw else None

        cs_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "id": cs_id,
            "space": space,
            "parent": parent_id,
            "base_head": base_head,
            "tree_hash": tree_hash,
            "author": author,
            "approver": approver,
            "run_id": run_id,
            "message": message,
            "draft_id": draft_id,
            "provenance": list(provenance or []),
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
            raise RebaseRequiredError(
                f"{exc}; actual_head={actual.decode() if actual else None}"
            ) from exc

        self._drafts.mark_published_in_txn(txn, draft_id, cs_id)
        append_in_txn(
            txn,
            {
                "event": "publish",
                "source": source,
                "actor": author,
                "approver": approver,
                "run_id": run_id,
                "space": space,
                "draft_id": draft_id,
                "changeset_id": cs_id,
                "tree_hash": tree_hash,
            },
        )
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
            message="нужен rebase: перечитайте head и повторите publish",
        )
