from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_repository
from core.repo import Repository


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    repo_path = tmp_path / "repo"
    monkeypatch.setenv("DOCVAULT_REPO", str(repo_path))
    monkeypatch.setenv("DOCVAULT_CAPABILITY_SECRET", "ui-test-secret")
    get_repository.cache_clear()
    Repository.init(repo_path)
    return TestClient(create_app())


def test_ui_static_bundle_served() -> None:
    client = TestClient(create_app())
    for path, needle in (
        ("/ui/", "styles.css"),
        ("/ui/index.html", "app.js"),
        ("/ui/styles.css", ":root"),
        ("/ui/app.js", "verdict"),
    ):
        res = client.get(path)
        assert res.status_code == 200, path
        assert needle in res.text, path


def test_ui_hitl_api_matches_frontend_contract(api_client: TestClient) -> None:
    repo = get_repository()
    blob_hash = repo.blobs.put(b"sample")
    source_ref = f"blob:{blob_hash}"

    created = api_client.post(
        "/runs",
        json={
            "claims": [
                {
                    "text": "sample claim",
                    "quote": "sample",
                    "source_ref": source_ref,
                }
            ],
            "write": {"path": "docs/ui.md", "content": "# ui\n"},
        },
    )
    assert created.status_code == 200
    run_id = created.json()["id"]
    loaded = api_client.get(f"/runs/{run_id}")
    assert loaded.status_code == 200
    assert loaded.json().get("claims")

    verdict = api_client.post(
        f"/runs/{run_id}/verdicts",
        json={"verdict": "reject", "message": "hitl ui"},
        headers={"Idempotency-Key": f"hitl-{run_id}-reject"},
    )
    assert verdict.status_code == 200
