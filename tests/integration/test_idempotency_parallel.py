from concurrent.futures import ThreadPoolExecutor, as_completed
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


def test_parallel_write_doc_one_effect(api_client: TestClient) -> None:
    space = "default"
    headers = {"Idempotency-Key": "write-parallel"}

    def put_once() -> str:
        res = api_client.put(
            f"/changesets/{space}/doc/p.md",
            json={"content": "same"},
            headers=headers,
        )
        assert res.status_code == 200
        return res.json()["blob_hash"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(put_once) for _ in range(8)]
        hashes = {f.result() for f in as_completed(futures)}
    assert len(hashes) == 1
