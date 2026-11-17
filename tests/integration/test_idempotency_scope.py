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


def test_same_key_different_routes_no_reuse(api_client: TestClient) -> None:
    space = "default"
    key = "shared-key"
    w = api_client.put(
        f"/changesets/{space}/doc/a.md",
        json={"content": "a"},
        headers={"Idempotency-Key": key},
    )
    assert w.status_code == 200
    p = api_client.post(
        f"/changesets/{space}/publish",
        json={"message": "m", "author": "user:host"},
        headers={"Idempotency-Key": key},
    )
    assert p.status_code == 200


def test_same_key_different_fingerprint_mismatch(api_client: TestClient) -> None:
    space = "default"
    headers = {"Idempotency-Key": "pub-x"}
    api_client.put(
        f"/changesets/{space}/doc/x.md",
        json={"content": "1"},
        headers={"Idempotency-Key": "w-x"},
    )
    first = api_client.post(
        f"/changesets/{space}/publish",
        json={"message": "one", "author": "user:host"},
        headers=headers,
    )
    assert first.status_code == 200
    second = api_client.post(
        f"/changesets/{space}/publish",
        json={"message": "two", "author": "user:host"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error"] == "idempotency_mismatch"
