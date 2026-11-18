from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_repository
from broker.service import CapabilityBroker
from core.capability.revocation import RevocationStore
from core.capability.tokens import issue_token
from core.errors import AuthzError
from core.repo import Repository


def _prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repository:
    path = tmp_path / "repo"
    monkeypatch.setenv("DOCVAULT_REPO", str(path))
    monkeypatch.setenv("DOCVAULT_CAPABILITY_SECRET", "auth-test-secret")
    get_repository.cache_clear()
    return Repository.init(path)


def test_api_token_required_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare(tmp_path, monkeypatch)
    monkeypatch.setenv("DOCVAULT_API_TOKEN", "secret-token")
    client = TestClient(create_app())

    assert client.get("/changesets").status_code == 401
    assert client.get("/changesets", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = client.get("/changesets", headers={"Authorization": "Bearer secret-token"})
    assert ok.status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/ui/").status_code == 200


def test_api_open_without_configured_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare(tmp_path, monkeypatch)
    monkeypatch.delenv("DOCVAULT_API_TOKEN", raising=False)
    assert TestClient(create_app()).get("/changesets").status_code == 200


def test_revoked_token_is_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _prepare(tmp_path, monkeypatch)
    draft = repo.drafts.create("default", "user:host", None)
    token = issue_token(
        space="default",
        path_prefixes=["docs/"],
        ops=["ping"],
        draft_id=str(draft["id"]),
        jti="fixed-jti",
    )
    broker = CapabilityBroker(repo)
    assert broker.handle("ping", token, {}) == {"pong": True}

    RevocationStore(repo.kv).revoke("fixed-jti")
    with pytest.raises(AuthzError, match="отозван"):
        broker.handle("ping", token, {})
    repo.close()


def test_api_revoke_endpoint_blocks_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _prepare(tmp_path, monkeypatch)
    draft = repo.drafts.create("default", "user:host", None)
    token = issue_token(
        space="default",
        path_prefixes=["docs/"],
        ops=["ping"],
        draft_id=str(draft["id"]),
        jti="api-jti",
    )
    client = TestClient(create_app())
    response = client.post("/capability/revoke", json={"token": token})
    assert response.status_code == 200
    assert response.json()["jti"] == "api-jti"

    with pytest.raises(AuthzError, match="отозван"):
        CapabilityBroker(repo).handle("ping", token, {})
    repo.close()
