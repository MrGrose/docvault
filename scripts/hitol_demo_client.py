import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_repository
from core.repo import Repository


def main() -> None:
    repo = os.environ.get("DOCVAULT_REPO", "data/demo-hitol")
    if not Path(repo, ".docvault").exists():
        Repository.init(Path(repo))
    os.environ["DOCVAULT_REPO"] = repo
    get_repository.cache_clear()

    client = TestClient(create_app())
    store = get_repository()
    blob = store.blobs.put(b"fee 42 coins for standard")

    bad = client.post(
        "/runs",
        json={
            "claims": [{"text": "x", "quote": "999", "source_ref": f"blob:{blob}"}],
            "write": {"path": "docs/x.md", "content": "nope"},
        },
    )
    if bad.status_code != 422:
        msg = f"expected ungrounded, got {bad.status_code}"
        raise SystemExit(msg)

    weak = client.post(
        "/runs",
        json={
            "claims": [
                {
                    "text": "quantum enterprise fee",
                    "quote": "42 coins",
                    "source_ref": f"blob:{blob}",
                }
            ],
            "write": {"path": "docs/pricing.md", "content": "# ok\n"},
        },
    )
    body = weak.json()
    if weak.status_code != 200 or body.get("status") != "needs_human":
        raise SystemExit(f"expected needs_human: {weak.status_code} {body}")

    run_id = str(body["id"])
    pub = client.post(
        f"/runs/{run_id}/verdicts",
        json={"verdict": "accept", "message": "demo hitol"},
        headers={"Idempotency-Key": "demo-hitol-accept"},
    )
    if pub.status_code != 200 or not pub.json().get("changeset_id"):
        raise SystemExit(f"publish failed: {pub.text}")

    audit = client.get("/audit")
    print(
        json.dumps(
            {
                "run_id": run_id,
                "changeset_id": pub.json()["changeset_id"],
                "audit_records": len(audit.json().get("records", [])),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
