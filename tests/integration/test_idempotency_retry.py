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


def test_publish_retry_same_idempotency_key(api_client: TestClient) -> None:
    space = "default"
    api_client.put(
        f"/changesets/{space}/doc/readme.md",
        json={"content": "hello"},
        headers={"Idempotency-Key": "write-1"},
    )
    fp_body = {"message": "m1", "author": "user:host", "expected_head": None}
    headers = {"Idempotency-Key": "pub-1"}
    first = api_client.post(f"/changesets/{space}/publish", json=fp_body, headers=headers)
    assert first.status_code == 200
    cs_id = first.json()["changeset_id"]

    for _ in range(4):
        again = api_client.post(f"/changesets/{space}/publish", json=fp_body, headers=headers)
        assert again.status_code == 200
        assert again.json()["changeset_id"] == cs_id
