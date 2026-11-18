from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from core.errors import (
    ConflictError,
    IdempotencyMismatchError,
    IdempotencyRaceError,
    RebaseRequiredError,
)
from core.idempotency import store as store_module
from core.idempotency.store import IdempotencyStore
from core.kv import LmdbKv, WriteTxn

Handler = Callable[[WriteTxn], tuple[int, dict[str, Any]]]


def _handler(status: int = 200, body: dict[str, Any] | None = None) -> Handler:
    def run(_txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        return status, {"ok": True} if body is None else body

    return run


def _raise(exc: BaseException) -> Handler:
    def run(_txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        raise exc

    return run


def test_execute_stores_then_replays(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = IdempotencyStore(kv)

    first = store.execute("scope-1", "fp-1", _handler(201, {"id": "x"}))
    assert first == (201, {"id": "x"}, False)

    second = store.execute("scope-1", "fp-1", _handler(500))
    assert second == (201, {"id": "x"}, True)
    kv.close()


def test_replay_with_other_fingerprint_is_mismatch(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = IdempotencyStore(kv)
    store.execute("scope-1", "fp-1", _handler())

    with pytest.raises(IdempotencyMismatchError, match="idempotency_mismatch"):
        store.execute("scope-1", "fp-2", _handler())
    kv.close()


def test_empty_changes_become_conflict(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = IdempotencyStore(kv)

    with pytest.raises(ConflictError, match="нет изменений"):
        store.execute("scope-1", "fp-1", _raise(ValueError("нет изменений для коммита")))
    kv.close()


def test_other_value_error_propagates(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = IdempotencyStore(kv)

    with pytest.raises(ValueError, match="другая ошибка"):
        store.execute("scope-1", "fp-1", _raise(ValueError("другая ошибка")))
    kv.close()


def test_race_retries_are_exhausted(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = IdempotencyStore(kv)

    with pytest.raises(ConflictError, match="не удалось завершить запрос"):
        store.execute("scope-1", "fp-1", _raise(IdempotencyRaceError()))
    kv.close()


def test_rebase_error_is_not_retried(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    store = IdempotencyStore(kv)

    with pytest.raises(RebaseRequiredError):
        store.execute("scope-1", "fp-1", _raise(RebaseRequiredError("stale")))
    kv.close()


def test_expired_key_runs_handler_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_IDEMPOTENCY_TTL", "10")
    clock = {"now": 1000.0}
    monkeypatch.setattr(store_module, "_now", lambda: clock["now"])
    kv = LmdbKv.open(tmp_path / "db")
    store = IdempotencyStore(kv)

    assert store.execute("scope-1", "fp-1", _handler(200, {"v": 1})) == (200, {"v": 1}, False)
    assert store.execute("scope-1", "fp-1", _handler(500)) == (200, {"v": 1}, True)

    clock["now"] = 1011.0
    assert store.execute("scope-1", "fp-1", _handler(201, {"v": 2})) == (201, {"v": 2}, False)
    kv.close()


def test_purge_expired_removes_old_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_IDEMPOTENCY_TTL", "10")
    clock = {"now": 1000.0}
    monkeypatch.setattr(store_module, "_now", lambda: clock["now"])
    kv = LmdbKv.open(tmp_path / "db")
    store = IdempotencyStore(kv)
    store.execute("scope-1", "fp-1", _handler())
    store.execute("scope-2", "fp-2", _handler())

    assert store.purge_expired() == 0
    clock["now"] = 1020.0
    assert store.purge_expired() == 2
    kv.close()
