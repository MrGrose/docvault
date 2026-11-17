from pathlib import Path

import pytest

from core.audit.log import append_in_txn, list_records
from core.kv import LmdbKv
from core.runs.store import RunStore


def test_run_create_get_and_update(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    runs = RunStore(kv)

    run_id = runs.create({"space": "default", "status": "pending"})
    stored = runs.get(run_id)
    assert stored["id"] == run_id
    assert stored["status"] == "pending"

    updated = runs.update(run_id, {"status": "published", "verdict": "accept"})
    assert updated["status"] == "published"
    assert updated["verdict"] == "accept"
    assert updated["space"] == "default"
    kv.close()


def test_run_missing_raises_key_error(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    runs = RunStore(kv)

    with pytest.raises(KeyError, match="run не найден"):
        runs.get("missing")
    with pytest.raises(KeyError, match="run не найден"):
        runs.update("missing", {"status": "published"})
    kv.close()


def test_audit_append_and_list_with_filters(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")

    def append_two(txn: object) -> None:
        assert hasattr(txn, "put")
        append_in_txn(txn, {"event": "first"})  # type: ignore[arg-type]
        append_in_txn(txn, {"event": "second"})  # type: ignore[arg-type]

    kv.run_write(append_two)

    records = list_records(kv)
    assert [r["seq"] for r in records] == [1, 2]
    assert records[0]["event"] == "first"

    assert [r["seq"] for r in list_records(kv, from_seq=2)] == [2]
    assert [r["seq"] for r in list_records(kv, limit=1)] == [1]
    kv.close()


def test_audit_ignores_sequence_key(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    kv.put_new(b"audit:seq", b"5")

    assert list_records(kv) == []
    assert list_records(kv, from_seq=1) == []
    kv.close()
