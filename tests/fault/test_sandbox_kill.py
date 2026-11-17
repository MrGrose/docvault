import os

import pytest

pytest.importorskip("docker")


@pytest.mark.skipif(os.environ.get("RUN_FAULT_TESTS", "") != "1", reason="RUN_FAULT_TESTS=1")
def test_kill_running_container() -> None:
    from sandbox.docker_runtime import DockerRuntime

    try:
        runtime = DockerRuntime()
    except Exception as exc:
        pytest.skip(f"docker daemon недоступен: {exc}")

    image = os.environ.get("DOCVAULT_SANDBOX_IMAGE", "alpine:3.20")
    container_id = runtime.spawn_idle(image, ["sleep", "300"])
    assert container_id
    container = runtime._client.containers.get(container_id)
    try:
        runtime.kill(container_id)
        container.reload()
        assert container.status in ("exited", "dead", "removing")
    finally:
        container.remove(force=True)
