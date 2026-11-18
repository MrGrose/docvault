import json
import time
import uuid
from typing import Any, cast

from core.errors import AuthzError, ConflictError
from core.keys import draft_key
from core.kv import LmdbKv, WriteTxn


class DraftStore:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def create(
        self,
        space: str,
        owner: str,
        base_head: bytes | None = None,
        parent_draft: str | None = None,
        paths: dict[str, str] | None = None,
        conflicts: list[str] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        def body(txn: WriteTxn) -> None:
            result["draft"] = self.create_in_txn(
                txn,
                space=space,
                owner=owner,
                base_head=base_head,
                parent_draft=parent_draft,
                paths=paths,
                conflicts=conflicts,
            )

        self._kv.run_write(body)
        return cast(dict[str, Any], result["draft"])

    def create_in_txn(
        self,
        txn: WriteTxn,
        space: str,
        owner: str,
        base_head: bytes | None = None,
        parent_draft: str | None = None,
        paths: dict[str, str] | None = None,
        conflicts: list[str] | None = None,
    ) -> dict[str, Any]:
        draft_id = uuid.uuid4().hex
        draft: dict[str, Any] = {
            "id": draft_id,
            "space": space,
            "owner": owner,
            "base_head": base_head.decode() if base_head else None,
            "parent_draft": parent_draft,
            "paths": dict(paths or {}),
            "conflicts": list(conflicts or []),
            "status": "open",
            "changeset_id": None,
            "created_at": int(time.time()),
        }
        body = json.dumps(draft, ensure_ascii=False).encode("utf-8")
        txn.put_new(draft_key(draft_id), body)
        return draft

    def get(self, draft_id: str) -> dict[str, Any]:
        raw = self._kv.get(draft_key(draft_id))
        if raw is None:
            msg = f"draft не найден: {draft_id}"
            raise KeyError(msg)
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
        return data

    def get_in_txn(self, txn: WriteTxn, draft_id: str) -> dict[str, Any]:
        raw = txn.get(draft_key(draft_id))
        if raw is None:
            msg = f"draft не найден: {draft_id}"
            raise KeyError(msg)
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
        return data

    def _save_in_txn(self, txn: WriteTxn, draft: dict[str, Any]) -> None:
        body = json.dumps(draft, ensure_ascii=False).encode("utf-8")
        txn.put(draft_key(str(draft["id"])), body)

    def _check_open(self, draft: dict[str, Any], actor: str | None) -> None:
        if draft.get("status") != "open":
            msg = f"draft не открыт: {draft.get('status')}"
            raise ConflictError(msg)
        if actor is not None and str(draft.get("owner")) != actor:
            msg = "draft принадлежит другому владельцу"
            raise AuthzError(msg)

    def put_path_in_txn(
        self,
        txn: WriteTxn,
        draft_id: str,
        path: str,
        blob_hash: str,
        actor: str | None = None,
    ) -> dict[str, Any]:
        draft = self.get_in_txn(txn, draft_id)
        self._check_open(draft, actor)
        paths = dict(draft.get("paths") or {})
        paths[path] = blob_hash
        draft["paths"] = paths
        if path in (draft.get("conflicts") or []):
            draft["conflicts"] = [p for p in draft["conflicts"] if p != path]
        self._save_in_txn(txn, draft)
        return draft

    def mark_published_in_txn(self, txn: WriteTxn, draft_id: str, cs_id: str) -> None:
        draft = self.get_in_txn(txn, draft_id)
        draft["status"] = "published"
        draft["changeset_id"] = cs_id
        self._save_in_txn(txn, draft)

    def rebase(
        self,
        draft_id: str,
        new_base: bytes | None,
        base_tree: dict[str, str],
        head_tree: dict[str, str],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        def body(txn: WriteTxn) -> None:
            result["draft"] = self.rebase_in_txn(txn, draft_id, new_base, base_tree, head_tree)

        self._kv.run_write(body)
        return cast(dict[str, Any], result["draft"])

    def rebase_in_txn(
        self,
        txn: WriteTxn,
        draft_id: str,
        new_base: bytes | None,
        base_tree: dict[str, str],
        head_tree: dict[str, str],
    ) -> dict[str, Any]:
        draft = self.get_in_txn(txn, draft_id)
        if draft.get("status") != "open":
            msg = f"draft не открыт: {draft.get('status')}"
            raise ConflictError(msg)
        paths = dict(draft.get("paths") or {})
        conflicts: list[str] = []
        for path, blob_hash in paths.items():
            base_blob = base_tree.get(path)
            head_blob = head_tree.get(path)
            if blob_hash == base_blob:
                continue
            if head_blob != base_blob:
                conflicts.append(path)
        return self.create_in_txn(
            txn,
            space=str(draft["space"]),
            owner=str(draft["owner"]),
            base_head=new_base,
            parent_draft=draft_id,
            paths=paths,
            conflicts=conflicts,
        )
