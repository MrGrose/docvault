import sys
import types
from typing import Any

import pytest

from sandbox.docker_runtime import DockerRuntime


class _FakeContainer:
    def __init__(self, status: dict[str, Any], container_id: str = "cid123") -> None:
        self.id = container_id
        self._status = status
        self.wait_timeout: int | None = None
        self.killed = False

    def wait(self, timeout: int) -> dict[str, Any]:
        self.wait_timeout = timeout
        return self._status

    def kill(self) -> None:
        self.killed = True


class _FakeContainers:
    def __init__(self, container: _FakeContainer) -> None:
        self._container = container
        self.run_calls: list[tuple[str, dict[str, Any]]] = []
        self.get_calls: list[str] = []

    def run(self, image: str, **kwargs: Any) -> _FakeContainer:
        self.run_calls.append((image, kwargs))
        return self._container

    def get(self, container_id: str) -> _FakeContainer:
        self.get_calls.append(container_id)
        return self._container


class _FakeClient:
    def __init__(self, container: _FakeContainer) -> None:
        self.containers = _FakeContainers(container)


def _install_fake_docker(monkeypatch: pytest.MonkeyPatch, client: _FakeClient) -> None:
    module = types.SimpleNamespace(from_env=lambda: client)
    monkeypatch.setitem(sys.modules, "docker", module)


def test_run_sets_isolation_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    container = _FakeContainer({"StatusCode": 7})
    client = _FakeClient(container)
    _install_fake_docker(monkeypatch, client)

    runtime = DockerRuntime()
    result = runtime.run(
        "agent:latest",
        ["python", "main.py"],
        {"A": "B"},
        {"/host/work": "/work"},
    )

    assert result.container_id == "cid123"
    assert result.exit_code == 7
    image, kwargs = client.containers.run_calls[0]
    assert image == "agent:latest"
    assert kwargs["command"] == ["python", "main.py"]
    assert kwargs["environment"] == {"A": "B"}
    assert kwargs["network_mode"] == "none"
    assert kwargs["working_dir"] == "/work"
    assert kwargs["mem_limit"] == "256m"
    assert kwargs["nano_cpus"] == 500_000_000
    assert kwargs["user"] == "1000:1000"
    assert kwargs["security_opt"] == ["no-new-privileges:true"]
    assert kwargs["volumes"] == {"/host/work": {"bind": "/work", "mode": "rw"}}
    assert container.wait_timeout == 120


def test_run_honours_env_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCVAULT_SANDBOX_MEM", "512m")
    monkeypatch.setenv("DOCVAULT_SANDBOX_CPU", "1.5")
    monkeypatch.setenv("DOCVAULT_SANDBOX_TIMEOUT", "5")
    monkeypatch.setenv("DOCVAULT_SANDBOX_USER", "0:0")

    container = _FakeContainer({"StatusCode": 0})
    client = _FakeClient(container)
    _install_fake_docker(monkeypatch, client)

    result = DockerRuntime().run("img", ["true"], {}, {})

    assert result.exit_code == 0
    _, kwargs = client.containers.run_calls[0]
    assert kwargs["mem_limit"] == "512m"
    assert kwargs["nano_cpus"] == 1_500_000_000
    assert kwargs["user"] == "0:0"
    assert container.wait_timeout == 5


def test_run_defaults_to_125_without_status_code(monkeypatch: pytest.MonkeyPatch) -> None:
    container = _FakeContainer({})
    _install_fake_docker(monkeypatch, _FakeClient(container))

    result = DockerRuntime().run("img", ["true"], {}, {})

    assert result.exit_code == 125


def test_kill_and_spawn_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    container = _FakeContainer({"StatusCode": 0})
    client = _FakeClient(container)
    _install_fake_docker(monkeypatch, client)
    runtime = DockerRuntime()

    runtime.kill("cid123")
    assert client.containers.get_calls == ["cid123"]
    assert container.killed is True

    spawned = runtime.spawn_idle("img", ["sleep", "60"])
    assert spawned == "cid123"
    _, kwargs = client.containers.run_calls[0]
    assert kwargs["network_mode"] == "none"
    assert kwargs["detach"] is True
