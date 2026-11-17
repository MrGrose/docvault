import hashlib
import json
from typing import Any


def build_scope_id(
    *,
    method: str,
    route_template: str,
    operation: str,
    owner: str,
    client_key: str,
) -> str:
    raw = f"{method}|{route_template}|{operation}|{owner}|{client_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint_json(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
