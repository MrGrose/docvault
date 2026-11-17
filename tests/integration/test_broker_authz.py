import time
import uuid
from pathlib import Path

import pytest

from broker.service import CapabilityBroker
from broker.uds_server import UdsBrokerServer
from core.capability.tokens import issue_token
from core.repo import Repository
from sandbox.sdk_client import SandboxSdkClient


def _short_socket_path() -> str:
    return f"/tmp/dvbrk-{uuid.uuid4().hex[:12]}.sock"


@pytest.fixture()
def broker_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    monkeypatch.setenv("DOCVAULT_CAPABILITY_SECRET", "broker-test-secret")
    repo = tmp_path / "repo"
    Repository.init(repo)
    sock = _short_socket_path()
    server = UdsBrokerServer(sock, CapabilityBroker(Repository.open(repo)))
    server.start_background()
    time.sleep(0.1)
    yield sock, "default"
    server.stop()


def test_write_doc_ok(broker_env: tuple[str, str]) -> None:
    sock, space = broker_env
    token = issue_token(space=space, path_prefixes=["docs/"], ops=["write_doc", "ping"])
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


def test_path_outside_prefix(broker_env: tuple[str, str]) -> None:
    sock, space = broker_env
    token = issue_token(space=space, path_prefixes=["docs/"], ops=["write_doc"])
    client = SandboxSdkClient(sock)
    with pytest.raises(RuntimeError, match="префиксов"):
        client.write_doc(
            token=token,
            space=space,
            path="secret/key.pem",
            content="x",
            idempotency_key="b2",
        )


def test_method_not_allowed(broker_env: tuple[str, str]) -> None:
    sock, space = broker_env
    token = issue_token(space=space, path_prefixes=["docs/"], ops=["ping"])
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
    token = issue_token(space="default", path_prefixes=["docs/"], ops=["ping"])
    with pytest.raises((TimeoutError, FileNotFoundError, OSError)):
        client.ping(token)
