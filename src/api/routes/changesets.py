from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_idempotency, get_repository
from api.middleware.idempotency import run_idempotent
from core.errors import ConflictError, RebaseRequiredError
from core.keys import DEFAULT_OWNER, DEFAULT_SPACE
from core.kv import WriteTxn
from core.repo import Repository

router = APIRouter(prefix="/changesets", tags=["changesets"])

MUTATING_ROUTES_REQUIRE_IDEM = (
    "PUT /changesets/{id}/doc/{path}",
    "POST /changesets/{id}/publish",
)


class CreateChangesetBody(BaseModel):
    space: str = Field(default=DEFAULT_SPACE)


class PublishBody(BaseModel):
    message: str = "publish via api"
    author: str = DEFAULT_OWNER
    expected_head: str | None = None


class WriteDocBody(BaseModel):
    content: str


def _repo() -> Repository:
    return get_repository()


@router.post("")
def create_changeset(body: CreateChangesetBody) -> dict[str, Any]:
    repo = _repo()
    head = repo.pointers.head(body.space)
    return {
        "id": body.space,
        "space": body.space,
        "head": head.decode() if head else None,
    }


@router.put("/{changeset_id}/doc/{path:path}")
def put_doc(
    changeset_id: str,
    path: str,
    body: WriteDocBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key обязателен")

    repo = _repo()
    space = changeset_id
    payload = {"path": path, "content": body.content, "space": space}

    def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        blob_hash = repo.blobs.put_in_txn(txn, body.content.encode("utf-8"))
        repo.work.set_path_in_txn(txn, space, path, blob_hash)
        return 200, {"path": path, "blob_hash": blob_hash}

    return run_idempotent(
        get_idempotency(),
        method="PUT",
        route_template="/changesets/{id}/doc/{path}",
        operation="write_doc",
        owner=DEFAULT_OWNER,
        client_key=idempotency_key,
        payload=payload,
        handler=handler,
    )


@router.post("/{changeset_id}/publish")
def publish(
    changeset_id: str,
    body: PublishBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key обязателен")

    repo = _repo()
    space = changeset_id
    payload = body.model_dump()
    expected = body.expected_head.encode() if body.expected_head else repo.pointers.head(space)

    def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        try:
            cs_id = repo.changesets.commit_working_copy_in_txn(
                txn,
                space,
                message=body.message,
                author=body.author,
                expected_head=expected,
            )
        except ConflictError as exc:
            hint = repo.changesets.rebase_hint(space, expected)
            raise RebaseRequiredError(str(exc) + "; " + hint.message) from exc
        return 200, {"changeset_id": cs_id, "space": space}

    return run_idempotent(
        get_idempotency(),
        method="POST",
        route_template="/changesets/{id}/publish",
        operation="publish",
        owner=DEFAULT_OWNER,
        client_key=idempotency_key,
        payload=payload,
        handler=handler,
    )
