import json
from pathlib import Path
from typing import Any, cast

from core.keys import DEFAULT_OWNER, DEFAULT_SPACE, cs_key, head_key
from core.kv import LmdbKv
from core.storage import BlobStore, ChangesetStore, DraftStore, PointerStore


class Repository:
    def __init__(self, root: Path, kv: LmdbKv) -> None:
        self.root = root
        self.kv = kv
        self.pointers = PointerStore(kv)
        self.blobs = BlobStore(kv)
        self.drafts = DraftStore(kv)
        self.changesets = ChangesetStore(kv, self.pointers, self.blobs, self.drafts)

    @classmethod
    def open(cls, repo_path: Path) -> "Repository":
        repo_path.mkdir(parents=True, exist_ok=True)
        marker = repo_path / ".docvault"
        if not marker.exists():
            raise FileNotFoundError("репозиторий не инициализирован, сначала dv init")
        kv = LmdbKv.open(repo_path / "lmdb")
        return cls(repo_path, kv)

    @classmethod
    def init(cls, repo_path: Path) -> "Repository":
        repo_path.mkdir(parents=True, exist_ok=True)
        marker = repo_path / ".docvault"
        marker.write_text("docvault\n", encoding="utf-8")
        kv = LmdbKv.open(repo_path / "lmdb")
        return cls(repo_path, kv)

    def close(self) -> None:
        self.kv.close()

    def write_draft(
        self,
        draft_id: str,
        path: str,
        content: str,
        actor: str | None = None,
    ) -> str:
        result: dict[str, str] = {}

        def body(txn: Any) -> None:
            blob_hash = self.blobs.put_in_txn(txn, content.encode("utf-8"))
            self.drafts.put_path_in_txn(txn, draft_id, path, blob_hash, actor)
            result["blob_hash"] = blob_hash

        self.kv.run_write(body)
        return result["blob_hash"]

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
        return self.changesets.publish_draft(
            draft_id,
            expected_head=expected_head,
            message=message,
            author=author,
            approver=approver,
            run_id=run_id,
            provenance=provenance,
            source=source,
        )

    def tree_at(self, ref: str | bytes) -> dict[str, str]:
        cs_id = ref.decode() if isinstance(ref, bytes) else ref
        cs = self.changesets.get(cs_id)
        return self.blobs.read_tree(str(cs["tree_hash"]))

    def tree_at_in_txn(self, txn: Any, ref: str | bytes) -> dict[str, str]:
        cs_id = ref.decode() if isinstance(ref, bytes) else ref
        raw = txn.get(cs_key(cs_id))
        if raw is None:
            msg = f"changeset не найден: {cs_id}"
            raise KeyError(msg)
        cs = json.loads(raw.decode("utf-8"))
        return self.blobs.read_tree(str(cs["tree_hash"]))

    def head_tree(self, space: str) -> dict[str, str]:
        head = self.pointers.head(space)
        if head is None:
            return {}
        return self.tree_at(head)

    def rebase_draft(self, draft_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {}

        def body(txn: Any) -> None:
            result["draft"] = self.rebase_draft_in_txn(txn, draft_id)

        self.kv.run_write(body)
        return cast(dict[str, Any], result["draft"])

    def rebase_draft_in_txn(self, txn: Any, draft_id: str) -> dict[str, Any]:
        draft = self.drafts.get_in_txn(txn, draft_id)
        base_head = draft.get("base_head")
        base_tree = self.tree_at_in_txn(txn, str(base_head)) if base_head else {}
        head_raw = txn.get(head_key(str(draft["space"])))
        head_tree = self.tree_at_in_txn(txn, head_raw) if head_raw is not None else {}
        return self.drafts.rebase_in_txn(
            txn,
            draft_id,
            head_raw,
            base_tree,
            head_tree,
        )

    @staticmethod
    def default_space() -> str:
        return DEFAULT_SPACE

    @staticmethod
    def default_owner() -> str:
        return DEFAULT_OWNER
