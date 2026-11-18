from typing import Any

from core.audit.log import append_in_txn
from core.capability.revocation import RevocationStore
from core.capability.tokens import (
    CapabilityClaims,
    assert_op_allowed,
    assert_path_allowed,
    token_fingerprint,
    verify_token,
)
from core.errors import AuthzError, ConflictError, IdempotencyMismatchError
from core.idempotency import build_scope_id, fingerprint_json
from core.idempotency.store import IdempotencyStore
from core.keys import DEFAULT_OWNER
from core.kv import WriteTxn
from core.metrics import inc
from core.repo import Repository

ALLOWED_METHODS = frozenset({"write_doc", "ping"})


class CapabilityBroker:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo
        self._idem = IdempotencyStore(repo.kv)
        self._revoked = RevocationStore(repo.kv)

    def handle(self, method: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._dispatch(method, token, params)
        except AuthzError:
            inc("docvault_broker_denied_total")
            raise

    def _dispatch(self, method: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
        if method not in ALLOWED_METHODS:
            raise AuthzError(f"method не в whitelist: {method}")
        if method == "ping":
            self._verify(token)
            return {"pong": True}

        claims = self._verify(token)
        assert_op_allowed(claims, method)

        if method == "write_doc":
            return self._write_doc(claims, token, params)
        msg = f"неподдерживаемый method: {method}"
        raise AuthzError(msg)

    def _verify(self, token: str) -> CapabilityClaims:
        claims = verify_token(token)
        if claims.jti and self._revoked.is_revoked(claims.jti):
            raise AuthzError("token отозван")
        return claims

    def _write_doc(
        self,
        claims: CapabilityClaims,
        token: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if not claims.run_id:
            raise AuthzError("token без run_id")
        supplied_run = str(params.get("run_id", ""))
        if supplied_run != claims.run_id:
            raise AuthzError("run_id не совпадает с token")
        space = str(params.get("space", claims.space))
        if space != claims.space:
            raise AuthzError("space не совпадает с token")
        draft_id = claims.draft_id
        if not draft_id:
            raise AuthzError("draft_id обязателен в token")
        path = str(params.get("path", ""))
        content = str(params.get("content", ""))
        idem_key = str(params.get("idempotency_key", ""))
        if not idem_key:
            raise AuthzError("idempotency_key обязателен")
        assert_path_allowed(claims, path)

        repo = self._repo
        try:
            draft = repo.drafts.get(draft_id)
        except KeyError as exc:
            raise AuthzError(str(exc)) from exc
        if draft.get("space") != space:
            raise AuthzError("draft не принадлежит space")
        if draft.get("status") != "open":
            raise AuthzError("draft не открыт")

        payload = {
            "space": space,
            "draft_id": draft_id,
            "path": path,
            "content": content,
            "token_fp": token_fingerprint(token),
        }
        fingerprint = fingerprint_json(payload)
        scope_id = build_scope_id(
            method="BROKER",
            route_template="uds/write_doc",
            operation="write_doc",
            owner=DEFAULT_OWNER,
            client_key=f"{draft_id}:{idem_key}",
        )

        def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
            blob_hash = repo.write_draft_in_txn(txn, draft_id, path, content)
            append_in_txn(
                txn,
                {
                    "event": "broker_write",
                    "source": "agent",
                    "actor": claims.agent_id or "agent",
                    "run_id": claims.run_id,
                    "space": space,
                    "draft_id": draft_id,
                    "path": path,
                    "blob_hash": blob_hash,
                },
            )
            return 200, {
                "path": path,
                "blob_hash": blob_hash,
                "space": space,
                "draft_id": draft_id,
            }

        try:
            _status, body, _replay = self._idem.execute(scope_id, fingerprint, handler)
        except (ConflictError, IdempotencyMismatchError) as exc:
            raise AuthzError(str(exc)) from exc
        return body
