from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_repository
from core.repo import Repository


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DOCVAULT_REPO", str(tmp_path / "repo"))
    get_repository.cache_clear()
    Repository.init(tmp_path / "repo")
    return TestClient(create_app())


def test_hitl_accept_writes_audit_and_changeset(api_client: TestClient) -> None:
    repo = get_repository()
    blob_hash = repo.blobs.put(b"monthly fee is 42 coins")
    body = {
        "space": "default",
        "claims": [
            {
                "text": "fee is 42 coins",
                "quote": "42 coins",
                "source_ref": f"blob:{blob_hash}",
            }
        ],
        "write": {"path": "docs/pricing.md", "content": "# pricing\n42\n"},
    }
    created = api_client.post("/runs", json=body)
    assert created.status_code == 200
    run_id = created.json()["id"]
    verdict = api_client.post(
        f"/runs/{run_id}/verdicts",
        json={"verdict": "accept", "message": "audit test"},
        headers={"Idempotency-Key": "hitl-audit-1"},
    )
    assert verdict.status_code == 200
    assert verdict.json().get("changeset_id")

    audit = api_client.get("/audit?from_seq=1")
    assert audit.status_code == 200
    records = audit.json()["records"]
    assert any(r.get("event") == "hitl_publish" for r in records)
