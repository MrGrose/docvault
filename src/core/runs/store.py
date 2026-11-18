import json
import time
import uuid
from typing import Any

from core.keys import run_key
from core.kv import LmdbKv, WriteTxn


class RunStore:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def create(self, payload: dict[str, Any]) -> str:
        run_id = uuid.uuid4().hex
        record = {**payload, "id": run_id, "created_at": int(time.time())}
        self._kv.put_new(run_key(run_id), json.dumps(record, ensure_ascii=False).encode("utf-8"))
        return run_id

    def list(
        self,
        space: str | None = None,
        status: str | None = None,
        draft_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for _, raw in self._kv.scan(run_key("")):
            data: dict[str, Any] = json.loads(raw.decode("utf-8"))
            if space is not None and data.get("space") != space:
                continue
            if status is not None and data.get("status") != status:
                continue
            if draft_id is not None and data.get("draft_id") != draft_id:
                continue
            items.append(data)
        items.sort(key=lambda d: int(d.get("created_at") or 0), reverse=True)
        return items[:limit]

    def get(self, run_id: str) -> dict[str, Any]:
        raw = self._kv.get(run_key(run_id))
        if raw is None:
            msg = f"run не найден: {run_id}"
            raise KeyError(msg)
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
        return data

    def update(self, run_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        def body(txn: WriteTxn) -> dict[str, Any]:
            raw = txn.get(run_key(run_id))
            if raw is None:
                msg = f"run не найден: {run_id}"
                raise KeyError(msg)
            current: dict[str, Any] = json.loads(raw.decode("utf-8"))
            merged = {**current, **patch}
            txn.put(run_key(run_id), json.dumps(merged, ensure_ascii=False).encode("utf-8"))
            return merged

        return self._kv.run_write(body)
