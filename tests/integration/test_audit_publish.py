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
    publishes = [r for r in records if r.get("event") == "publish"]
    assert len(publishes) == 1
    assert publishes[0]["source"] == "hitl"
    assert publishes[0]["approver"] == "user:host"
    stored = repo.drafts.get(draft["id"])
    assert stored["status"] == "published"
    cs = repo.changesets.get(str(publishes[0]["changeset_id"]))
    assert cs["provenance"][0]["path"] == "docs/pricing.md"
    assert cs["provenance"][0]["quote_hash"]


def test_api_publish_writes_one_audit_record(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "text", "w-api-1")
    api.publish_ok(draft["id"], None, "p-api-1")
    audit = api.client.get("/audit").json()["records"]
    publishes = [r for r in audit if r.get("event") == "publish"]
    assert len(publishes) == 1
    assert publishes[0]["source"] == "api"
    assert publishes[0]["actor"] == "user:host"
    repo = get_repository()
    cs = repo.changesets.get(str(publishes[0]["changeset_id"]))
    assert cs["provenance"][0]["path"] == "docs/a.md"
    assert cs["provenance"][0]["blob_hash"]
    assert cs["provenance"][0]["source"] == "api"


def test_metrics_endpoint_reports_publish(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/m.md", "text", "w-metrics")
    api.publish_ok(draft["id"], None, "p-metrics")
    res = api.client.get("/metrics")
    assert res.status_code == 200
    assert "docvault_publish_total" in res.text
    assert "docvault_publish_api_total" in res.text
