import json
from dataclasses import dataclass
from typing import Any


@dataclass
class BrokerRequest:
    req_id: str
    method: str
    token: str
    params: dict[str, Any]


@dataclass
class BrokerResponse:
    req_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_line(self) -> bytes:
        body: dict[str, Any] = {"id": self.req_id, "ok": self.ok}
        if self.ok:
            body["result"] = self.result or {}
        else:
            body["error"] = self.error or "error"
        return (json.dumps(body, ensure_ascii=False) + "\n").encode("utf-8")


def parse_request(line: bytes) -> BrokerRequest:
    data = json.loads(line.decode("utf-8"))
    return BrokerRequest(
        req_id=str(data.get("id", "")),
        method=str(data.get("method", "")),
        token=str(data.get("token", "")),
        params=dict(data.get("params", {})),
    )
