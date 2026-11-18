from collections.abc import Iterator
from pathlib import Path

import pytest

from agent.claims import Claim, check_change_binding, validate_claim_for_change
from core.kv import LmdbKv
from core.storage.blob_store import BlobStore


@pytest.fixture()
def blobs(tmp_path: Path) -> Iterator[BlobStore]:
    kv = LmdbKv.open(tmp_path / "db")
    yield BlobStore(kv)
    kv.close()


def test_binding_uses_changed_fragment(blobs: BlobStore) -> None:
    blob = blobs.put(b"fee is 42 coins")
    claim = Claim(
        "fee is 42 coins",
        "42 coins",
        f"blob:{blob}",
        path="docs/a.md",
    )
    old = "# pricing\n\nold line"
    new = "# pricing\n\nfee is 42 coins"
    result = validate_claim_for_change(claim, old, new, blobs)
    assert result.status == "grounded"
    assert result.binding == "ok"


def test_same_text_elsewhere_is_not_binding(blobs: BlobStore) -> None:
    blob = blobs.put(b"fee is 42 coins")
    claim = Claim("fee is 42 coins", "42 coins", f"blob:{blob}", path="docs/a.md")
    old = "fee is 42 coins\n\nold paragraph"
    new = "fee is 42 coins\n\nnew paragraph"
    result = validate_claim_for_change(claim, old, new, blobs)
    assert result.status == "needs_human"
    assert result.binding == "needs_human"


def test_quote_from_other_document_does_not_bind(blobs: BlobStore) -> None:
    blob = blobs.put(b"other document quote")
    claim = Claim("some claim", "other document quote", f"blob:{blob}", path="docs/a.md")
    result = validate_claim_for_change(claim, "old", "new", blobs)
    assert result.status == "needs_human"
    assert result.binding == "needs_human"


def test_paraphrase_goes_to_human(blobs: BlobStore) -> None:
    blob = blobs.put(b"the monthly fee is 42 coins")
    claim = Claim(
        "cost is 42 units",
        "monthly fee is 42 coins",
        f"blob:{blob}",
        path="docs/a.md",
    )
    result = validate_claim_for_change(claim, "old", "cost is 42 units", blobs)
    assert result.status == "needs_human"
    assert result.support == "weak"


def test_delete_claim_binds_removed_fragment(blobs: BlobStore) -> None:
    blob = blobs.put(b"old tariff line")
    claim = Claim(
        "old tariff line",
        "old tariff line",
        f"blob:{blob}",
        path="docs/a.md",
        change_kind="delete",
    )
    result = validate_claim_for_change(claim, "old tariff line\n\nkeep", "keep", blobs)
    assert result.status == "grounded"
    assert result.binding == "ok"


def test_byte_range_must_match(blobs: BlobStore) -> None:
    blob = blobs.put(b"0123456789")
    claim = Claim(
        "2345",
        "2345",
        f"blob:{blob}",
        path="docs/a.md",
        byte_range=(2, 6),
    )
    assert validate_claim_for_change(claim, "", "2345", blobs).status == "grounded"
    wrong = Claim(
        "2345",
        "2345",
        f"blob:{blob}",
        path="docs/a.md",
        byte_range=(1, 5),
    )
    assert validate_claim_for_change(wrong, "", "2345", blobs).status == "blocked"


def test_binding_without_path_is_human(blobs: BlobStore) -> None:
    assert check_change_binding(Claim("x", "x", "blob:0"), "a", "b") == (
        "needs_human",
        "claim без path",
    )
