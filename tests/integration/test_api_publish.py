from typing import Any


def test_publish_empty_draft_returns_clear_conflict(api: Any) -> None:
    draft = api.draft()
    response = api.publish(draft["id"], None, "empty-1", "empty")
    assert response.status_code == 409
    assert response.json() == {"error": "conflict", "detail": "нет изменений для коммита"}


def test_publish_requires_matching_base_head(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "v1", "w1")
    response = api.publish(draft["id"], "0" * 32, "p1")
    assert response.status_code == 409
    assert "base_head" in response.json()["detail"]


def test_publish_stale_draft_requires_rebase(api: Any) -> None:
    first = api.draft()
    api.write_ok(first["id"], "docs/a.md", "v1", "w1")
    head = api.publish_ok(first["id"], None, "p1", "first")

    mine = api.draft()
    api.write_ok(mine["id"], "docs/b.md", "v2", "w2")

    other = api.draft()
    api.write_ok(other["id"], "docs/c.md", "v3", "w3")
    api.publish_ok(other["id"], head, "p3", "other")

    stale = api.publish(mine["id"], head, "p2", "stale")
    assert stale.status_code == 409
    assert stale.json()["error"] == "rebase_required"

    rebased = api.client.post(
        f"/changesets/{mine['id']}/rebase",
        headers={"Idempotency-Key": "r1"},
    )
    assert rebased.status_code == 201
    new_draft = rebased.json()["draft"]
    assert new_draft["parent_draft"] == mine["id"]

    head_now = api.client.get("/docs/tree", params={"space": "default"}).json()["head"]
    ok = api.publish(new_draft["id"], head_now, "p4", "after rebase")
    assert ok.status_code == 200


def test_create_draft_returns_base_head(api: Any) -> None:
    draft = api.draft()
    assert draft["base_head"] is None
    assert draft["space"] == "default"
    fetched = api.client.get(f"/changesets/{draft['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == draft["id"]


def test_write_to_foreign_draft_is_rejected(api: Any) -> None:
    draft = api.draft(owner="user:other")
    response = api.write(draft["id"], "docs/a.md", "x", "w-foreign")
    assert response.status_code == 403
    assert response.json()["error"] == "authz"


def test_work_key_is_not_used(api: Any) -> None:
    from api.deps import get_repository

    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "v1", "w-nokey")
    api.publish_ok(draft["id"], None, "p-nokey")
    assert get_repository().kv.get(b"work:default") is None


def test_publish_without_expected_head_returns_422(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "v1", "w-nohead")
    response = api.client.post(
        f"/changesets/{draft['id']}/publish",
        json={"message": "no head", "author": "user:host"},
        headers={"Idempotency-Key": "p-nohead"},
    )
    assert response.status_code == 422


def test_write_doc_requires_idempotency_key(api: Any) -> None:
    draft = api.draft()
    response = api.client.put(
        f"/changesets/{draft['id']}/doc/docs/a.md",
        json={"content": "x"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Idempotency-Key обязателен"
