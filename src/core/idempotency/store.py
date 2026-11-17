import json
from collections.abc import Callable
from typing import Any

from core.errors import (
    ConflictError,
    IdempotencyMismatchError,
    IdempotencyRaceError,
    RebaseRequiredError,
    UngroundedError,
)
from core.keys import idem_key
from core.kv import LmdbKv, WriteTxn


class IdempotencyStore:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def _replay(self, scope_id: str, fingerprint: str) -> tuple[int, dict[str, Any], bool] | None:
        raw = self._kv.get(idem_key(scope_id))
        if raw is None:
            return None
        record: dict[str, Any] = json.loads(raw.decode("utf-8"))
        if str(record.get("fingerprint")) != fingerprint:
            raise IdempotencyMismatchError("idempotency_mismatch")
        return (
            int(record.get("status_code", 200)),
            dict(record.get("body", {})),
            True,
        )

    def execute(
        self,
        scope_id: str,
        fingerprint: str,
        handler: Callable[[WriteTxn], tuple[int, dict[str, Any]]],
    ) -> tuple[int, dict[str, Any], bool]:
        for _ in range(8):
            replay = self._replay(scope_id, fingerprint)
            if replay is not None:
                return replay
            try:
                return self._execute_once(scope_id, fingerprint, handler)
            except IdempotencyRaceError:
                continue
            except (RebaseRequiredError, UngroundedError, IdempotencyMismatchError):
                raise
        replay = self._replay(scope_id, fingerprint)
        if replay is not None:
            return replay
        msg = "idempotency: не удалось завершить запрос"
        raise ConflictError(msg)

    def _execute_once(
        self,
        scope_id: str,
        fingerprint: str,
        handler: Callable[[WriteTxn], tuple[int, dict[str, Any]]],
    ) -> tuple[int, dict[str, Any], bool]:
        def body(txn: WriteTxn) -> tuple[int, dict[str, Any], bool]:
            key = idem_key(scope_id)
            raw = txn.get(key)
            if raw is not None:
                record: dict[str, Any] = json.loads(raw.decode("utf-8"))
                if str(record.get("fingerprint")) != fingerprint:
                    raise IdempotencyMismatchError("idempotency_mismatch")
                return (
                    int(record.get("status_code", 200)),
                    dict(record.get("body", {})),
                    True,
                )

            try:
                status_code, outcome = handler(txn)
            except ValueError as exc:
                if "нет изменений" in str(exc):
                    raise ConflictError("нет изменений для коммита") from exc
                raise

            stored = {
                "fingerprint": fingerprint,
                "status_code": status_code,
                "body": outcome,
            }
            try:
                txn.put_new(key, json.dumps(stored, ensure_ascii=False).encode("utf-8"))
            except ConflictError as exc:
                raise IdempotencyRaceError from exc
            return status_code, outcome, False

        return self._kv.run_write(body)
