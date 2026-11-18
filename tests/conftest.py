from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_repository
from core.repo import Repository


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DOCVAULT_REPO", str(tmp_path / "repo"))
    get_repository.cache_clear()
    Repository.init(tmp_path / "repo")
    yield TestClient(create_app())
    get_repository.cache_clear()


class Api:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def draft(self, space: str = "default", owner: str = "user:host") -> dict[str, Any]:
        response = self.client.post("/changesets", json={"space": space, "owner": owner})
        assert response.status_code == 201, response.text
        return dict(response.json())

    def write(
        self,
        draft_id: str,
        path: str,
        content: str,
        key: str,
    ):
        return self.client.put(
            f"/changesets/{draft_id}/doc/{path}",
            json={"content": content},
            headers={"Idempotency-Key": key},
        )

    def publish(
        self,
        draft_id: str,
        expected_head: str | None,
        key: str,
        message: str = "publish",
        author: str = "user:host",
    ):
        head = expected_head or "genesis"
        return self.client.post(
            f"/changesets/{draft_id}/publish",
            json={"message": message, "author": author, "expected_head": head},
            headers={"Idempotency-Key": key},
        )

    def publish_ok(
        self,
        draft_id: str,
        expected_head: str | None,
        key: str,
        message: str = "publish",
    ) -> str:
        response = self.publish(draft_id, expected_head, key, message)
        assert response.status_code == 200, response.text
        return str(response.json()["changeset_id"])

    def write_ok(self, draft_id: str, path: str, content: str, key: str) -> None:
        response = self.write(draft_id, path, content, key)
        assert response.status_code == 200, response.text


@pytest.fixture()
def api(api_client: TestClient) -> Api:
    return Api(api_client)
