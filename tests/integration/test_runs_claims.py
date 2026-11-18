from typing import Any

from api.deps import get_repository


def test_run_grounds_claim_bound_to_changed_fragment(api: Any) -> None:
    repo = get_repository()
    source = repo.blobs.put(b"monthly fee is 42 coins")
    draft = api.draft()
    api.write_ok(
        draft["id"],
        "docs/pricing.md",
        "# pricing\n\nmonthly fee is 42 coins\n",
        "w-run-1",
    )
    created = api.client.post(
        "/runs",
        json={
            "draft_id": draft["id"],
            "claims": [
                {
                    "text": "monthly fee is 42 coins",
                    "quote": "42 coins",
                    "source_ref": f"blob:{source}",
                    "path": "docs/pricing.md",
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "grounded"
    run = api.client.get(f"/runs/{body['id']}").json()
    assert run["human_review_required"] is True
    assert run["expected_head"] == "genesis"
    assert "docs/pricing.md" in run["documents"]
    assert run["documents"]["docs/pricing.md"]["new"].startswith("# pricing")
    assert any(line.startswith("+") for line in run["diff"]["docs/pricing.md"])


def test_run_rejects_claim_path_outside_changes(api: Any) -> None:
    repo = get_repository()
    source = repo.blobs.put(b"some quote")
    draft = api.draft()
    api.write_ok(draft["id"], "docs/pricing.md", "new text", "w-run-2")
    created = api.client.post(
        "/runs",
        json={
            "draft_id": draft["id"],
            "claims": [
                {
                    "text": "some quote",
                    "quote": "some quote",
                    "source_ref": f"blob:{source}",
                    "path": "docs/other.md",
                }
            ],
        },
    )
    assert created.status_code == 422
    assert "не входит в изменения" in created.text


def test_run_marks_unbound_claim_for_human(api: Any) -> None:
    repo = get_repository()
    source = repo.blobs.put(b"monthly fee is 42 coins")
    draft = api.draft()
    api.write_ok(draft["id"], "docs/pricing.md", "unrelated paragraph", "w-run-3")
    created = api.client.post(
        "/runs",
        json={
            "draft_id": draft["id"],
            "claims": [
                {
                    "text": "monthly fee is 42 coins",
                    "quote": "42 coins",
                    "source_ref": f"blob:{source}",
                    "path": "docs/pricing.md",
                }
            ],
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "needs_human"
