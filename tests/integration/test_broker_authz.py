import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from broker.service import CapabilityBroker
from broker.uds_server import UdsBrokerServer
from core.capability.tokens import issue_token
from core.keys import DEFAULT_SPACE
from core.repo import Repository
from sandbox.sdk_client import SandboxSdkClient


def _short_socket_path() -> str:
    return f"/tmp/dvbrk-{uuid.uuid4().hex[:12]}.sock"


@pytest.fixture()
def broker_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[str, str, str, Path]]:
    monkeypatch.setenv("DOCVAULT_CAPABILITY_SECRET", "broker-test-secret")
    repo = tmp_path / "repo"
    handle = Repository.init(repo)
    draft = handle.drafts.create(DEFAULT_SPACE, "user:host", None)
    sock = _short_socket_path()
    server = UdsBrokerServer(sock, CapabilityBroker(handle))
    server.start_background()
    time.sleep(0.1)
    yield sock, DEFAULT_SPACE, str(draft["id"]), repo
    server.stop()


def test_write_doc_ok(broker_env: tuple[str, str, str, Path]) -> None:
    sock, space, draft_id, repo_path = broker_env
    token = issue_token(
        space=space,
        path_prefixes=["docs/"],
        ops=["write_doc", "ping"],
        draft_id=draft_id,
    )
    client = SandboxSdkClient(sock)
    assert client.ping(token)
    res = client.write_doc(
        token=token,
        space=space,
        path="docs/tariffs.md",
        content="tariff line",
        idempotency_key="b1",
    )
    assert res["path"] == "docs/tariffs.md"
    assert "blob_hash" in res
    assert res["draft_id"] == draft_id


def test_path_outside_prefix(broker_env: tuple[str, str, str, Path]) -> None:
    sock, space, draft_id, repo_path = broker_env
    token = issue_token(
        space=space,
        path_prefixes=["docs/"],
        ops=["write_doc"],
        draft_id=draft_id,
    )
    client = SandboxSdkClient(sock)
    with pytest.raises(RuntimeError, match="префиксов"):
        client.write_doc(
            token=token,
            space=space,
            path="secret/key.pem",
            content="x",
            idempotency_key="b2",
        )


def test_method_not_allowed(broker_env: tuple[str, str, str, Path]) -> None:
    sock, space, draft_id, repo_path = broker_env
    token = issue_token(
        space=space,
        path_prefixes=["docs/"],
        ops=["ping"],
        draft_id=draft_id,
    )
    client = SandboxSdkClient(sock)
    with pytest.raises(RuntimeError):
        client.write_doc(
            token=token,
            space=space,
            path="docs/a.md",
            content="x",
            idempotency_key="b3",
        )


def test_broker_down_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_CAPABILITY_SECRET", "broker-test-secret")
    missing = f"/tmp/dvbrk-missing-{uuid.uuid4().hex[:8]}.sock"
    client = SandboxSdkClient(missing, timeout=0.2)
    token = issue_token(
        space="default",
        path_prefixes=["docs/"],
        ops=["ping"],
        draft_id="draft-1",
    )
    with pytest.raises((TimeoutError, FileNotFoundError, OSError)):
        client.ping(token)


def test_write_to_closed_draft_is_denied(broker_env: tuple[str, str, str, Path]) -> None:
    sock, space, draft_id, repo_path = broker_env
    repo = Repository.open(repo_path)
    draft = repo.drafts.get(draft_id)
    repo.write_draft(draft_id, "docs/a.md", "x")
    base = draft["base_head"].encode() if draft["base_head"] else None
    repo.publish_draft(draft_id, base, "m", "user:host")
    repo.close()
    token = issue_token(
        space=space,
        path_prefixes=["docs/"],
        ops=["write_doc"],
        draft_id=draft_id,
    )
    client = SandboxSdkClient(sock)
    with pytest.raises(RuntimeError, match="не открыт"):
        client.write_doc(
            token=token,
            space=space,
            path="docs/a.md",
            content="y",
            idempotency_key="b-closed",
        )


def test_token_for_other_space_is_denied(broker_env: tuple[str, str, str, Path]) -> None:
    sock, space, draft_id, repo_path = broker_env
    token = issue_token(
        space="other",
        path_prefixes=["docs/"],
        ops=["write_doc"],
        draft_id=draft_id,
    )
    client = SandboxSdkClient(sock)
    with pytest.raises(RuntimeError, match="space"):
        client.write_doc(
            token=token,
            space=space,
            path="docs/a.md",
            content="x",
            idempotency_key="b-space",
        )
