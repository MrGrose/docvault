from typing import Any


def test_publish_retry_same_idempotency_key(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "readme.md", "hello", "write-1")
    body = {"message": "m1", "author": "user:host", "expected_head": "genesis"}
    headers = {"Idempotency-Key": "pub-1"}
    first = api.client.post(f"/changesets/{draft['id']}/publish", json=body, headers=headers)
    assert first.status_code == 200, first.text
    cs_id = first.json()["changeset_id"]

    for _ in range(4):
        again = api.client.post(f"/changesets/{draft['id']}/publish", json=body, headers=headers)
        assert again.status_code == 200
        assert again.json()["changeset_id"] == cs_id

    audit = api.client.get("/audit").json()["records"]
    assert len([r for r in audit if r.get("event") == "publish"]) == 1
