import json
import os
import socket
import uuid
from typing import Any


class SandboxSdkClient:
    def __init__(self, socket_path: str, timeout: float = 5.0) -> None:
        self._path = socket_path
        self._timeout = timeout

    def call(self, method: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
        req_id = uuid.uuid4().hex
        payload = {"id": req_id, "method": method, "token": token, "params": params}
        line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self._timeout)
        try:
            sock.connect(self._path)
            sock.sendall(line)
            buffer = b""
            while b"\n" not in buffer:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buffer += chunk
            data = json.loads(buffer.decode("utf-8").strip())
        finally:
            sock.close()
        if not data.get("ok"):
            msg = str(data.get("error", "broker error"))
            raise RuntimeError(msg)
        result = data.get("result")
        if not isinstance(result, dict):
            return {}
        return result

    def write_doc(
        self,
        token: str,
        space: str,
        path: str,
        content: str,
        idempotency_key: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        bound_run = run_id or os.environ.get("DOCVAULT_RUN_ID", "")
        params = {
            "space": space,
            "path": path,
            "content": content,
            "idempotency_key": idempotency_key,
        }
        if bound_run:
            params["run_id"] = bound_run
        return self.call("write_doc", token, params)

    def ping(self, token: str) -> bool:
        res = self.call("ping", token, {})
        return bool(res.get("pong"))
