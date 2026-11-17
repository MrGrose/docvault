from pathlib import Path

import pytest

from agent.claims import Claim, check_claim_support, validate_claim
from core.repo import Repository


@pytest.fixture()
def repo(tmp_path: Path) -> Repository:
    return Repository.init(tmp_path / "repo")


def test_evidence_fail_blocks_before_support() -> None:
    claim = Claim(text="a", quote="b", source_ref="blob:missing")
    res = check_claim_support(claim, evidence_ok=False)
    assert res.status == "blocked"


def test_weak_support_needs_human(repo: Repository) -> None:
    blob_hash = repo.blobs.put(b"unrelated warehouse inventory list")
    claim = Claim(
        text="pricing tier enterprise unlimited",
        quote="warehouse inventory",
        source_ref=f"blob:{blob_hash}",
    )
    res = validate_claim(claim, repo.blobs)
    assert res.status == "needs_human"


def test_token_overlap_ok(repo: Repository) -> None:
    blob_hash = repo.blobs.put(b"Standard plan price 100 USD monthly")
    claim = Claim(
        text="Standard plan costs 100 USD",
        quote="price 100 USD monthly",
        source_ref=f"blob:{blob_hash}",
    )
    res = validate_claim(claim, repo.blobs)
    assert res.status == "ok"
