from pathlib import Path

import pytest

from agent.claims import Claim, check_evidence_integrity
from core.repo import Repository


@pytest.fixture()
def repo(tmp_path: Path) -> Repository:
    return Repository.init(tmp_path / "repo")


def test_quote_must_be_substring(repo: Repository) -> None:
    blob_hash = repo.blobs.put(b"tariff plan starts at 100 USD per month")
    claim = Claim(
        text="price is 100 USD",
        quote="100 USD per month",
        source_ref=f"blob:{blob_hash}",
    )
    result = check_evidence_integrity(claim, repo.blobs)
    assert result.status == "grounded"


def test_fabricated_quote_blocked(repo: Repository) -> None:
    blob_hash = repo.blobs.put(b"tariff plan starts at 100 USD")
    claim = Claim(
        text="price is 999 USD",
        quote="999 USD",
        source_ref=f"blob:{blob_hash}",
    )
    result = check_evidence_integrity(claim, repo.blobs)
    assert result.status == "blocked"


def test_bad_source_ref(repo: Repository) -> None:
    claim = Claim(text="x", quote="y", source_ref="blob:00" * 16)
    result = check_evidence_integrity(claim, repo.blobs)
    assert result.status == "blocked"
