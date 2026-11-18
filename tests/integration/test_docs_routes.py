from typing import Any


def _publish_one(api: Any) -> str:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/offer.md", "# Оффер\n\nТариф 100 рублей.\n", "docs-w1")
    return api.publish_ok(draft["id"], None, "docs-p1", "оффер")


def test_tree_is_empty_without_head(api_client: Any) -> None:
    response = api_client.get("/docs/tree", params={"space": "default"})
    assert response.status_code == 200
    assert response.json() == {"space": "default", "head": None, "paths": {}}


def test_doc_requires_head(api_client: Any) -> None:
    response = api_client.get("/docs/doc/docs/offer.md", params={"space": "default"})
    assert response.status_code == 404
    assert response.json()["detail"] == "head не задан"


def test_tree_and_doc_after_publish(api: Any) -> None:
    head = _publish_one(api)

    tree = api.client.get("/docs/tree", params={"space": "default"}).json()
    assert tree["head"] == head
    assert "docs/offer.md" in tree["paths"]

    doc = api.client.get("/docs/doc/docs/offer.md", params={"space": "default"})
    assert doc.status_code == 200
    assert doc.json()["content"].startswith("# Оффер")
    assert doc.json()["path"] == "docs/offer.md"


def test_missing_doc_returns_404(api: Any) -> None:
    _publish_one(api)
    response = api.client.get("/docs/doc/docs/missing.md", params={"space": "default"})
    assert response.status_code == 404
    assert response.json()["detail"] == "документ не найден"


def test_create_draft_reports_base_head(api: Any) -> None:
    empty = api.draft()
    assert empty["base_head"] is None

    head = _publish_one(api)
    filled = api.draft()
    assert filled["id"] != empty["id"]
    assert filled["base_head"] == head


def test_write_doc_requires_idempotency_key(api: Any) -> None:
    draft = api.draft()
    response = api.client.put(
        f"/changesets/{draft['id']}/doc/docs/offer.md",
        json={"content": "x"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Idempotency-Key обязателен"
