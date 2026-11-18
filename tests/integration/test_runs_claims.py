from typing import Any

from api.deps import get_repository
from core.runs.store import RunStore


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


def test_run_unknown_draft_returns_404(api: Any) -> None:
    response = api.client.post(
        "/runs",
        json={"draft_id": "missing", "claims": []},
    )
    assert response.status_code == 404


def test_run_closed_draft_returns_409(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "text", "w-closed")
    api.publish_ok(draft["id"], None, "p-closed")
    response = api.client.post(
        "/runs",
        json={"draft_id": draft["id"], "claims": []},
    )
    assert response.status_code == 409


def test_get_missing_run_returns_404(api: Any) -> None:
    assert api.client.get("/runs/missing").status_code == 404


def test_verdict_reject_does_not_need_expected_head(api: Any) -> None:
    draft = api.draft()
    created = api.client.post(
        "/runs",
        json={"draft_id": draft["id"], "claims": []},
    )
    assert created.status_code == 200
    run_id = created.json()["id"]
    response = api.client.post(
        f"/runs/{run_id}/verdicts",
        json={"verdict": "reject"},
        headers={"Idempotency-Key": "reject-1"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_verdict_accept_requires_expected_head(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "text", "w-verdict")
    created = api.client.post(
        "/runs",
        json={"draft_id": draft["id"], "claims": []},
    )
    run_id = created.json()["id"]
    response = api.client.post(
        f"/runs/{run_id}/verdicts",
        json={"verdict": "accept"},
        headers={"Idempotency-Key": "accept-nohead"},
    )
    assert response.status_code == 422


def test_run_view_without_draft(api: Any) -> None:
    repo = get_repository()
    run_id = RunStore(repo.kv).create({"space": "default", "status": "grounded"})
    view = api.client.get(f"/runs/{run_id}").json()
    assert view["human_review_required"] is True
    assert "documents" not in view


def test_run_view_with_missing_draft(api: Any) -> None:
    repo = get_repository()
    run_id = RunStore(repo.kv).create(
        {"space": "default", "status": "grounded", "draft_id": "missing"}
    )
    view = api.client.get(f"/runs/{run_id}").json()
    assert view["human_review_required"] is True
    assert "documents" not in view


def test_run_view_truncates_large_document(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/big.md", "x" * 200_001, "w-big")
    created = api.client.post(
        "/runs",
        json={"draft_id": draft["id"], "claims": []},
    )
    run_id = created.json()["id"]
    view = api.client.get(f"/runs/{run_id}").json()
    assert view["documents"]["docs/big.md"]["truncated"] is True


def test_verdict_rejects_content_changed_after_run(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "first", "w-before-run")
    created = api.client.post(
        "/runs",
        json={"draft_id": draft["id"], "claims": []},
    )
    run_id = created.json()["id"]
    api.write_ok(draft["id"], "docs/a.md", "second", "w-after-run")

    response = api.client.post(
        f"/runs/{run_id}/verdicts",
        json={"verdict": "accept", "expected_head": "genesis"},
        headers={"Idempotency-Key": "accept-stale"},
    )
    assert response.status_code == 409
    assert "изменился" in response.text
    assert api.client.get(f"/changesets/{draft['id']}").json()["status"] == "open"


def test_list_runs_returns_latest_first(api: Any) -> None:
    draft = api.draft()
    first = api.client.post("/runs", json={"draft_id": draft["id"], "claims": []}).json()
    second = api.client.post("/runs", json={"draft_id": draft["id"], "claims": []}).json()
    listed = api.client.get(f"/runs?draft_id={draft['id']}").json()["items"]
    ids = [item["id"] for item in listed]
    assert set(ids) == {first["id"], second["id"]}
    assert listed[0]["claims"] == 0
    assert api.client.get("/runs?status=missing").json()["items"] == []


def test_run_candidates_lists_changed_paragraphs(api: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "# A\n\nПервое.\n\nВторое.\n", "w-cand")
    created = api.client.post("/runs", json={"draft_id": draft["id"], "claims": []})
    run_id = created.json()["id"]

    items = api.client.get(f"/runs/{run_id}/candidates").json()["items"]
    texts = {item["text"] for item in items}
    assert "Первое." in texts
    assert "Второе." in texts
    assert all(item["change_kind"] == "add" for item in items)
    assert api.client.get("/runs/missing/candidates").status_code == 404
