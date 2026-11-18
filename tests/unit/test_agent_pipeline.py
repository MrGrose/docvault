from pathlib import Path

import pytest

from agent.claims import Claim
from agent.pipeline import run_draft_stage, run_pipeline, validation_status_for_claims
from core.kv import LmdbKv
from core.storage.blob_store import BlobStore


def test_draft_stage_returns_sdk_code() -> None:
    code = run_draft_stage("update_tariffs")
    assert "SandboxSdkClient" in code
    assert "write_doc" in code


def test_draft_stage_rejects_unknown_task() -> None:
    with pytest.raises(ValueError, match="неизвестная задача"):
        run_draft_stage("delete_everything")


def test_pipeline_delegates_to_draft_stage() -> None:
    assert run_pipeline("update_tariffs") == run_draft_stage("update_tariffs")


def test_validation_status_ok_for_grounded_claim(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    blobs = BlobStore(kv)
    source = "тариф на обслуживание составляет 100 рублей"
    blob_hash = blobs.put(source.encode("utf-8"))

    claim = Claim(text="тариф 100 рублей", quote="100 рублей", source_ref=blob_hash)
    status, results = validation_status_for_claims([claim], blobs)
    assert status == "grounded"
    assert results[0].status == "grounded"
    kv.close()


def test_validation_status_blocked_for_fabricated_quote(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    blobs = BlobStore(kv)
    blob_hash = blobs.put("совсем другой текст".encode())

    claim = Claim(text="тариф 100 рублей", quote="100 рублей", source_ref=blob_hash)
    status, results = validation_status_for_claims([claim], blobs)
    assert status == "blocked"
    assert results[0].status == "blocked"
    kv.close()


def test_validation_status_needs_human_without_token_overlap(tmp_path: Path) -> None:
    kv = LmdbKv.open(tmp_path / "db")
    blobs = BlobStore(kv)
    blob_hash = blobs.put("условия оказания услуг".encode())

    claim = Claim(
        text="совершенно иные слова", quote="условия оказания услуг", source_ref=blob_hash
    )
    status, results = validation_status_for_claims([claim], blobs)
    assert status == "needs_human"
    assert results[0].status == "needs_human"
    kv.close()
