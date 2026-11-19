from typing import Any

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from api.deps import get_idempotency, get_repository
from api.middleware.idempotency import run_idempotent
from api.schemas import COMMON_RESPONSES
from core.keys import DEFAULT_OWNER, DEFAULT_SPACE
from core.kv import WriteTxn
from core.repo import Repository

router = APIRouter(prefix="/changesets", tags=["changesets"], responses=COMMON_RESPONSES)


class CreateChangesetBody(BaseModel):
    space: str = Field(default=DEFAULT_SPACE)
    owner: str = Field(default=DEFAULT_OWNER)


class PublishBody(BaseModel):
    message: str = "publish via api"
    author: str = DEFAULT_OWNER
    expected_head: str


class WriteDocBody(BaseModel):
    content: str


def _repo() -> Repository:
    return get_repository()


def _draft(repo: Repository, draft_id: str) -> dict[str, Any]:
    try:
        return repo.drafts.get(draft_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", status_code=201)
def create_changeset(body: CreateChangesetBody) -> dict[str, Any]:
    repo = _repo()
    head = repo.pointers.head(body.space)
    draft = repo.drafts.create(body.space, body.owner, head)
    return {
        "id": draft["id"],
        "space": draft["space"],
        "owner": draft["owner"],
        "base_head": draft["base_head"],
    }


@router.get("")
def list_drafts(
    space: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    drafts = _repo().drafts.list(space=space, status=status, limit=limit)
    return {
        "items": [
            {
                "id": draft["id"],
                "space": draft.get("space"),
                "owner": draft.get("owner"),
                "base_head": draft.get("base_head"),
                "status": draft.get("status"),
                "changeset_id": draft.get("changeset_id"),
                "created_at": draft.get("created_at"),
                "paths": sorted((draft.get("paths") or {}).keys()),
                "conflicts": draft.get("conflicts") or [],
            }
            for draft in drafts
        ]
    }


@router.get("/{draft_id}")
def get_draft(draft_id: str) -> dict[str, Any]:
    return _draft(_repo(), draft_id)


@router.put("/{draft_id}/doc/{path:path}")
def put_doc(
    draft_id: str,
    path: str,
    body: WriteDocBody,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, Any]:
    repo = _repo()
    draft = _draft(repo, draft_id)
    payload = {"draft_id": draft_id, "path": path, "content": body.content}

    def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        blob_hash = repo.write_draft_in_txn(txn, draft_id, path, body.content, DEFAULT_OWNER)
        return 200, {"path": path, "blob_hash": blob_hash, "draft_id": draft_id}

    status, result = run_idempotent(
        get_idempotency(),
        method="PUT",
        route_template="/changesets/{id}/doc/{path}",
        operation="write_doc",
        owner=str(draft["owner"]),
        client_key=idempotency_key,
        payload=payload,
        handler=handler,
    )
    response.status_code = status
    return result


@router.post("/{draft_id}/publish")
def publish(
    draft_id: str,
    body: PublishBody,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, Any]:
    repo = _repo()
    draft = _draft(repo, draft_id)
    expected = None if body.expected_head == "genesis" else body.expected_head.encode("utf-8")
    payload = {**body.model_dump(), "draft_id": draft_id}

    def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        cs_id = repo.changesets.publish_draft_in_txn(
            txn,
            draft_id,
            expected_head=expected,
            message=body.message,
            author=body.author,
        )
        return 200, {
            "changeset_id": cs_id,
            "space": draft["space"],
            "draft_id": draft_id,
        }

    status, result = run_idempotent(
        get_idempotency(),
        method="POST",
        route_template="/changesets/{id}/publish",
        operation="publish",
        owner=str(draft["owner"]),
        client_key=idempotency_key,
        payload=payload,
        handler=handler,
    )
    if "changeset_id" in result:
        repo.index_changeset(str(result["changeset_id"]))
    response.status_code = status
    return result


@router.post("/{draft_id}/rebase")
def rebase(
    draft_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, Any]:
    repo = _repo()
    draft = _draft(repo, draft_id)
    payload = {"draft_id": draft_id}

    def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        new_draft = repo.rebase_draft_in_txn(txn, draft_id)
        return 201, {"draft": new_draft}

    status, result = run_idempotent(
        get_idempotency(),
        method="POST",
        route_template="/changesets/{id}/rebase",
        operation="rebase",
        owner=str(draft["owner"]),
        client_key=idempotency_key,
        payload=payload,
        handler=handler,
    )
    response.status_code = status
    return result
