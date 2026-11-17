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


def test_publish_rebase_required_on_stale_head(api_client: TestClient) -> None:
    space = "default"
    api_client.put(
        f"/changesets/{space}/doc/a.md",
        json={"content": "v1"},
        headers={"Idempotency-Key": "w1"},
    )
    first = api_client.post(
        f"/changesets/{space}/publish",
        json={"message": "m1", "author": "user:host"},
        headers={"Idempotency-Key": "p1"},
    )
    head = first.json()["changeset_id"]

    api_client.put(
        f"/changesets/{space}/doc/b.md",
        json={"content": "v2"},
        headers={"Idempotency-Key": "w2"},
    )
    stale = api_client.post(
        f"/changesets/{space}/publish",
        json={
            "message": "m2",
            "author": "user:host",
            "expected_head": "0" * 32,
        },
        headers={"Idempotency-Key": "p2"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"] == "rebase_required"

    api_client.put(
        f"/changesets/{space}/doc/c.md",
        json={"content": "v3"},
        headers={"Idempotency-Key": "w3"},
    )
    ok = api_client.post(
        f"/changesets/{space}/publish",
        json={"message": "m3", "author": "user:host", "expected_head": head},
        headers={"Idempotency-Key": "p3"},
    )
    assert ok.status_code == 200
