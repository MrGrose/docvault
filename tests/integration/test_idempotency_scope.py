from typing import Any


def test_same_key_different_routes_no_reuse(api: Any) -> None:
    draft = api.draft()
    key = "shared-key"
    written = api.client.put(
        f"/changesets/{draft['id']}/doc/a.md",
        json={"content": "a"},
        headers={"Idempotency-Key": key},
    )
    assert written.status_code == 200, written.text
    published = api.client.post(
        f"/changesets/{draft['id']}/publish",
        json={"message": "m", "author": "user:host", "expected_head": "genesis"},
        headers={"Idempotency-Key": key},
    )
    assert published.status_code == 200, published.text


def test_same_key_different_fingerprint_mismatch(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "x.md", "1", "w-x")
    headers = {"Idempotency-Key": "pub-x"}
    first = api.client.post(
        f"/changesets/{draft['id']}/publish",
        json={"message": "one", "author": "user:host", "expected_head": "genesis"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    second = api.client.post(
        f"/changesets/{draft['id']}/publish",
        json={"message": "two", "author": "user:host", "expected_head": "genesis"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error"] == "idempotency_mismatch"
