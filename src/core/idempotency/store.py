import json
import os
import time
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


def _now() -> float:
    return time.time()


def _ttl_seconds() -> int:
    raw = os.environ.get("DOCVAULT_IDEMPOTENCY_TTL", "604800")
    try:
        return int(raw)
    except ValueError:
        return 604800


def _is_expired(record: dict[str, Any]) -> bool:
    ttl = _ttl_seconds()
    if ttl <= 0:
        return False
    expires_at = float(record.get("expires_at") or 0)
    return expires_at > 0 and _now() >= expires_at


class IdempotencyStore:
    def __init__(self, kv: LmdbKv) -> None:
        self._kv = kv

    def _replay(self, scope_id: str, fingerprint: str) -> tuple[int, dict[str, Any], bool] | None:
        raw = self._kv.get(idem_key(scope_id))
        if raw is None:
            return None
        record: dict[str, Any] = json.loads(raw.decode("utf-8"))
        if _is_expired(record):
            return None
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
            expired = False
            if raw is not None:
                record: dict[str, Any] = json.loads(raw.decode("utf-8"))
                expired = _is_expired(record)
                if not expired:
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

            now = _now()
            ttl = _ttl_seconds()
            stored = {
                "fingerprint": fingerprint,
                "status_code": status_code,
                "body": outcome,
                "created_at": now,
                "expires_at": now + ttl if ttl > 0 else 0,
            }
            encoded = json.dumps(stored, ensure_ascii=False).encode("utf-8")
            if expired:
                txn.put(key, encoded)
            else:
                try:
                    txn.put_new(key, encoded)
                except ConflictError as exc:
                    raise IdempotencyRaceError from exc
            return status_code, outcome, False

        return self._kv.run_write(body)

    def purge_expired(self) -> int:
        keys: list[bytes] = []
        for key, raw in self._kv.scan(idem_key("")):
            record: dict[str, Any] = json.loads(raw.decode("utf-8"))
            if _is_expired(record):
                keys.append(key)
        if not keys:
            return 0

        removed = 0

        def body(txn: WriteTxn) -> None:
            nonlocal removed
            for key in keys:
                raw = txn.get(key)
                if raw is None:
                    continue
                record: dict[str, Any] = json.loads(raw.decode("utf-8"))
                if _is_expired(record):
                    txn.delete(key)
                    removed += 1

        self._kv.run_write(body)
        return removed
