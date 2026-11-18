from typing import Any

from api.deps import get_repository


def test_hitl_accept_writes_audit_and_changeset(api: Any) -> None:
    repo = get_repository()
    blob_hash = repo.blobs.put(b"monthly fee is 42 coins")
    draft = api.draft()
    api.write_ok(
        draft["id"],
        "docs/pricing.md",
        "# pricing\n\nfee is 42 coins\n",
        "w-hitl-1",
    )
    created = api.client.post(
        "/runs",
        json={
            "space": "default",
            "draft_id": draft["id"],
            "claims": [
                {
                    "text": "fee is 42 coins",
                    "quote": "42 coins",
                    "source_ref": f"blob:{blob_hash}",
                    "path": "docs/pricing.md",
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    run_id = created.json()["id"]
    verdict = api.client.post(
        f"/runs/{run_id}/verdicts",
        json={
            "verdict": "accept",
            "message": "audit test",
            "expected_head": draft["base_head"] or "genesis",
        },
        headers={"Idempotency-Key": "hitl-audit-1"},
    )
    assert verdict.status_code == 200, verdict.text
    assert verdict.json().get("changeset_id")

    audit = api.client.get("/audit?from_seq=1")
    assert audit.status_code == 200
    records = audit.json()["records"]
    assert any(r.get("event") == "hitl_publish" for r in records)
    stored = repo.drafts.get(draft["id"])
    assert stored["status"] == "published"
