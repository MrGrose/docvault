import time

import pytest

from core.capability.tokens import issue_token, verify_token
from core.errors import AuthzError


@pytest.fixture(autouse=True)
def secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_CAPABILITY_SECRET", "unit-test-secret")


def test_issue_and_verify() -> None:
    token = issue_token(
        space="default",
        path_prefixes=["docs/"],
        ops=["write_doc"],
        draft_id="draft-1",
        ttl_seconds=60,
    )
    claims = verify_token(token)
    assert claims.space == "default"
    assert "write_doc" in claims.ops
    assert claims.draft_id == "draft-1"


def test_expired_token() -> None:
    token = issue_token(
        space="default",
        path_prefixes=["docs/"],
        ops=["write_doc"],
        draft_id="draft-1",
        ttl_seconds=1,
    )
    time.sleep(1.1)
    with pytest.raises(AuthzError, match="истек"):
        verify_token(token)


def test_tampered_token() -> None:
    token = issue_token(
        space="default",
        path_prefixes=["docs/"],
        ops=["write_doc"],
        draft_id="draft-1",
    )
    bad = token[:-1] + ("a" if token[-1] != "a" else "b")
    with pytest.raises(AuthzError):
        verify_token(bad)


def test_token_carries_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_CAPABILITY_SECRET", "s")
    token = issue_token(
        space="default",
        path_prefixes=["docs/"],
        ops=["write_doc"],
        draft_id="d1",
        run_id="run-9",
    )
    assert verify_token(token).run_id == "run-9"


def test_malformed_tokens_raise_authz_error() -> None:
    for token in ("", "a", "a.b", "ё.ё", "%%% .sig"):
        with pytest.raises(AuthzError):
            verify_token(token)
