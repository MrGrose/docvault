from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass
class RunResult:
    container_id: str
    exit_code: int


class SandboxRuntime(Protocol):
    def run(
        self,
        image: str,
        command: list[str],
        env: Mapping[str, str],
        mounts: Mapping[str, str],
        workdir: str = "/work",
    ) -> RunResult: ...

    def kill(self, container_id: str) -> None: ...
