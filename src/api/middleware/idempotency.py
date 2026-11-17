from collections.abc import Callable
from typing import Any

from core.idempotency import IdempotencyStore, build_scope_id, fingerprint_json
from core.kv import WriteTxn


def run_idempotent(
    idem: IdempotencyStore,
    *,
    method: str,
    route_template: str,
    operation: str,
    owner: str,
    client_key: str,
    payload: dict[str, Any],
    handler: Callable[[WriteTxn], tuple[int, dict[str, Any]]],
) -> dict[str, Any]:
    scope_id = build_scope_id(
        method=method,
        route_template=route_template,
        operation=operation,
        owner=owner,
        client_key=client_key,
    )
    fingerprint = fingerprint_json(payload)
    status, body, _replayed = idem.execute(scope_id, fingerprint, handler)
    if status != 200:
        return body
    return body
