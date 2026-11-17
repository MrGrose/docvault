from typing import Any

from core.capability.tokens import (
    CapabilityClaims,
    assert_op_allowed,
    assert_path_allowed,
    verify_token,
)
from core.errors import AuthzError, ConflictError, IdempotencyMismatchError
from core.idempotency import build_scope_id, fingerprint_json
from core.idempotency.store import IdempotencyStore
from core.keys import DEFAULT_OWNER
from core.kv import WriteTxn
from core.repo import Repository

ALLOWED_METHODS = frozenset({"write_doc", "ping"})


class CapabilityBroker:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo
        self._idem = IdempotencyStore(repo.kv)

    def handle(self, method: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
        if method not in ALLOWED_METHODS:
            raise AuthzError(f"method не в whitelist: {method}")
        if method == "ping":
            verify_token(token)
            return {"pong": True}

        claims = verify_token(token)
        assert_op_allowed(claims, method)

        if method == "write_doc":
            return self._write_doc(claims, token, params)
        msg = f"неподдерживаемый method: {method}"
        raise AuthzError(msg)

    def _write_doc(
        self,
        claims: CapabilityClaims,
        token: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        space = str(params.get("space", claims.space))
        if space != claims.space:
            raise AuthzError("space не совпадает с token")
        path = str(params.get("path", ""))
        content = str(params.get("content", ""))
        idem_key = str(params.get("idempotency_key", ""))
        if not idem_key:
            raise AuthzError("idempotency_key обязателен")
        assert_path_allowed(claims, path)

        payload = {
            "space": space,
            "path": path,
            "content": content,
            "token_fp": token[:16],
        }
        fingerprint = fingerprint_json(payload)
        scope_id = build_scope_id(
            method="BROKER",
            route_template="uds/write_doc",
            operation="write_doc",
            owner=DEFAULT_OWNER,
            client_key=idem_key,
        )

        repo = self._repo

        def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
            blob_hash = repo.blobs.put_in_txn(txn, content.encode("utf-8"))
            repo.work.set_path_in_txn(txn, space, path, blob_hash)
            return 200, {"path": path, "blob_hash": blob_hash, "space": space}

        try:
            _status, body, _replay = self._idem.execute(scope_id, fingerprint, handler)
        except (ConflictError, IdempotencyMismatchError) as exc:
            raise AuthzError(str(exc)) from exc
        return body
