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


def _publish_one(api_client: TestClient) -> str:
    api_client.put(
        "/changesets/default/doc/docs/offer.md",
        json={"content": "# Оффер\n\nТариф 100 рублей.\n"},
        headers={"Idempotency-Key": "docs-w1"},
    )
    published = api_client.post(
        "/changesets/default/publish",
        json={"message": "оффер", "author": "user:host"},
        headers={"Idempotency-Key": "docs-p1"},
    )
    assert published.status_code == 200
    return str(published.json()["changeset_id"])


def test_tree_is_empty_without_head(api_client: TestClient) -> None:
    response = api_client.get("/docs/tree", params={"space": "default"})
    assert response.status_code == 200
    assert response.json() == {"space": "default", "head": None, "paths": {}}


def test_doc_requires_head(api_client: TestClient) -> None:
    response = api_client.get("/docs/doc/docs/offer.md", params={"space": "default"})
    assert response.status_code == 404
    assert response.json()["detail"] == "head не задан"


def test_tree_and_doc_after_publish(api_client: TestClient) -> None:
    head = _publish_one(api_client)

    tree = api_client.get("/docs/tree", params={"space": "default"}).json()
    assert tree["head"] == head
    assert "docs/offer.md" in tree["paths"]

    doc = api_client.get("/docs/doc/docs/offer.md", params={"space": "default"})
    assert doc.status_code == 200
    assert doc.json()["content"].startswith("# Оффер")
    assert doc.json()["path"] == "docs/offer.md"


def test_missing_doc_returns_404(api_client: TestClient) -> None:
    _publish_one(api_client)
    response = api_client.get("/docs/doc/docs/missing.md", params={"space": "default"})
    assert response.status_code == 404
    assert response.json()["detail"] == "документ не найден"


def test_create_changeset_reports_current_head(api_client: TestClient) -> None:
    empty = api_client.post("/changesets", json={"space": "default"}).json()
    assert empty["head"] is None

    head = _publish_one(api_client)
    filled = api_client.post("/changesets", json={"space": "default"}).json()
    assert filled["id"] == "default"
    assert filled["head"] == head


def test_write_doc_requires_idempotency_key(api_client: TestClient) -> None:
    response = api_client.put(
        "/changesets/default/doc/docs/offer.md",
        json={"content": "x"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Idempotency-Key обязателен"
