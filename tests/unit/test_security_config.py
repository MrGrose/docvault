from pathlib import Path

import pytest

from core.capability.tokens import issue_token, token_fingerprint
from core.errors import StorageFullError
from core.kv import LmdbKv


def test_token_fingerprints_differ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_CAPABILITY_SECRET", "fingerprint-secret")
    first = issue_token(
        space="default",
        path_prefixes=["docs/"],
        ops=["write_doc"],
        draft_id="draft-1",
    )
    second = issue_token(
        space="default",
        path_prefixes=["other/"],
        ops=["ping"],
        draft_id="draft-2",
    )
    assert token_fingerprint(first) != token_fingerprint(second)
    assert len(token_fingerprint(first)) == 16


def test_compose_binds_localhost() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:8000:8000" in text
    assert '"8000:8000"' not in text


def test_map_full_raises_domain_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCVAULT_MAP_SIZE", "1048576")
    kv = LmdbKv.open(tmp_path / "small")
    try:
        with pytest.raises(StorageFullError):
            kv.put_new(b"big", b"x" * 2_000_000)
    finally:
        kv.close()
