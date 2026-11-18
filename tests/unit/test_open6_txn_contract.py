from pathlib import Path


def test_idempotency_store_uses_run_write() -> None:
    src = Path("src/core/idempotency/store.py").read_text(encoding="utf-8")
    assert "run_write" in src
    assert "Callable[[WriteTxn]" in src.replace(" ", "")


def test_api_handlers_take_write_txn() -> None:
    src = Path("src/api/routes/changesets.py").read_text(encoding="utf-8")
    assert "write_draft_in_txn" in src
    assert "publish_draft_in_txn" in src


def test_broker_uses_repository_write() -> None:
    src = Path("src/broker/service.py").read_text(encoding="utf-8")
    assert "write_draft_in_txn" in src
