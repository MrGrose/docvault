from typing import Any

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from agent.claims import Claim
from agent.stages.validate import aggregate_status, validate_claims_for_change
from api.deps import get_idempotency, get_repository
from api.middleware.idempotency import run_idempotent
from core.audit.log import append_in_txn
from core.errors import UngroundedError
from core.keys import DEFAULT_OWNER, DEFAULT_SPACE
from core.kv import WriteTxn
from core.repo import Repository
from core.runs.store import RunStore

router = APIRouter(prefix="/runs", tags=["runs"])


class ClaimModel(BaseModel):
    text: str
    quote: str
    source_ref: str
    path: str = ""
    change_kind: str = "add"
    byte_range: tuple[int, int] | None = None


class CreateRunBody(BaseModel):
    space: str = Field(default=DEFAULT_SPACE)
    draft_id: str
    claims: list[ClaimModel]


class VerdictBody(BaseModel):
    verdict: str
    message: str = "hitl publish"
    author: str = DEFAULT_OWNER
    expected_head: str | None = None


def _repo() -> Repository:
    return get_repository()


def _runs() -> RunStore:
    return RunStore(_repo().kv)


def _draft_documents(repo: Repository, draft: dict[str, Any]) -> dict[str, tuple[str, str]]:
    base_head = draft.get("base_head")
    base_tree = repo.tree_at(str(base_head)) if base_head else {}
    documents: dict[str, tuple[str, str]] = {}
    for path, blob_hash in dict(draft.get("paths") or {}).items():
        new = repo.blobs.read(str(blob_hash)).decode("utf-8")
        old_blob = base_tree.get(path)
        old = repo.blobs.read(old_blob).decode("utf-8") if old_blob else ""
        documents[path] = (old, new)
    return documents


@router.post("")
def create_run(body: CreateRunBody) -> dict[str, Any]:
    repo = _repo()
    try:
        draft = repo.drafts.get(body.draft_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if draft.get("status") != "open":
        raise HTTPException(status_code=409, detail="draft не открыт")

    claims = [
        Claim(
            c.text,
            c.quote,
            c.source_ref,
            path=c.path,
            change_kind=c.change_kind,
            byte_range=c.byte_range,
        )
        for c in body.claims
    ]
    documents = _draft_documents(repo, draft)
    for claim in claims:
        if claim.path and claim.path not in documents:
            raise HTTPException(
                status_code=422,
                detail=f"claim path не входит в изменения: {claim.path}",
            )
    results = validate_claims_for_change(claims, documents, repo.blobs)
    status = aggregate_status(results)
    if status == "blocked":
        raise HTTPException(
            status_code=422,
            detail={"error": "ungrounded", "validations": [r.__dict__ for r in results]},
        )

    run_id = _runs().create(
        {
            "space": body.space,
            "draft_id": body.draft_id,
            "base_head": draft.get("base_head"),
            "status": status,
            "claims": [c.__dict__ for c in claims],
            "validations": [r.__dict__ for r in results],
            "verdict": None,
            "changeset_id": None,
        }
    )
    return {"id": run_id, "status": status, "draft_id": body.draft_id}


@router.get("/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    try:
        return _runs().get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{run_id}/verdicts")
def post_verdict(
    run_id: str,
    body: VerdictBody,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key обязателен")

    run = _runs().get(run_id)
    if run.get("status") == "blocked":
        raise UngroundedError("run blocked, вердикт невозможен")

    if body.verdict == "reject":
        updated = _runs().update(run_id, {"status": "rejected", "verdict": "reject"})
        return {"id": run_id, "status": updated["status"]}

    if body.verdict != "accept":
        raise HTTPException(status_code=422, detail="verdict: accept|reject")

    if body.expected_head is None:
        raise HTTPException(status_code=422, detail="expected_head обязателен")
    draft_id = str(run.get("draft_id", ""))
    if not draft_id:
        raise HTTPException(status_code=422, detail="run без draft_id")
    space = str(run.get("space", DEFAULT_SPACE))
    repo = _repo()
    expected = None if body.expected_head == "genesis" else body.expected_head.encode("utf-8")
    payload = {**body.model_dump(), "run_id": run_id, "draft_id": draft_id}

    def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        cs_id = repo.changesets.publish_draft_in_txn(
            txn,
            draft_id,
            expected_head=expected,
            message=body.message,
            author=body.author,
            approver=body.author,
            run_id=run_id,
        )
        append_in_txn(
            txn,
            {
                "event": "hitl_publish",
                "run_id": run_id,
                "changeset_id": cs_id,
                "draft_id": draft_id,
                "space": space,
                "approver": body.author,
            },
        )
        return 200, {"changeset_id": cs_id, "run_id": run_id, "status": "published"}

    status, result = run_idempotent(
        get_idempotency(),
        method="POST",
        route_template="/runs/{id}/verdicts",
        operation="hitl_publish",
        owner=DEFAULT_OWNER,
        client_key=idempotency_key,
        payload=payload,
        handler=handler,
    )
    _runs().update(
        run_id,
        {
            "status": "published",
            "verdict": "accept",
            "changeset_id": result.get("changeset_id"),
        },
    )
    response.status_code = status
    return result
