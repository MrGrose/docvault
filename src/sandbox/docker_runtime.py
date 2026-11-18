import importlib
import os
from collections.abc import Mapping
from typing import Any

from sandbox.runtime import RunResult


class DockerRuntime:
    def __init__(self) -> None:
        docker_mod: Any = importlib.import_module("docker")
        self._client = docker_mod.from_env()

    def _limits(self) -> dict[str, Any]:
        return {
            "network_mode": "none",
            "mem_limit": os.environ.get("DOCVAULT_SANDBOX_MEM", "256m"),
            "nano_cpus": int(float(os.environ.get("DOCVAULT_SANDBOX_CPU", "0.5")) * 1e9),
            "pids_limit": int(os.environ.get("DOCVAULT_SANDBOX_PIDS", "64")),
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],
            "user": os.environ.get("DOCVAULT_SANDBOX_USER", "1000:1000"),
            "read_only": True,
            "tmpfs": {"/tmp": "rw,size=64m"},
            "detach": True,
            "remove": False,
        }

    def run(
        self,
        image: str,
        command: list[str],
        env: Mapping[str, str],
        mounts: Mapping[str, str],
        workdir: str = "/work",
    ) -> RunResult:
        volumes: dict[str, dict[str, str]] = {}
        for host_path, container_path in mounts.items():
            volumes[host_path] = {"bind": container_path, "mode": "rw"}
        environment = {"PYTHONDONTWRITEBYTECODE": "1", **env}
        container = self._client.containers.run(
            image,
            command=command,
            environment=environment,
            volumes=volumes,
            working_dir=workdir,
            **self._limits(),
        )
        try:
            result = container.wait(timeout=int(os.environ.get("DOCVAULT_SANDBOX_TIMEOUT", "120")))
            exit_code = int(result.get("StatusCode", 125))
            if exit_code != 0:
                print(container.logs().decode("utf-8", "replace"), flush=True)
            return RunResult(container_id=container.id or "", exit_code=exit_code)
        finally:
            container.remove(force=True)

    def spawn_idle(self, image: str, command: list[str]) -> str:
        container = self._client.containers.run(image, command=command, **self._limits())
        return container.id or ""

    def kill(self, container_id: str) -> None:
        c = self._client.containers.get(container_id)
        c.kill()
