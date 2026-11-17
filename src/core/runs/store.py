import json
import uuid
from typing import Any

from core.keys import run_key
from core.kv import LmdbKv, WriteTxn


class RunStore:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def create(self, payload: dict[str, Any]) -> str:
        run_id = uuid.uuid4().hex
        record = {**payload, "id": run_id}
        self._kv.put_new(run_key(run_id), json.dumps(record, ensure_ascii=False).encode("utf-8"))
        return run_id

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
