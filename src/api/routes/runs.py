from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from agent.claims import Claim
from agent.stages.validate import aggregate_status, validate_claims
from api.deps import get_idempotency, get_repository
from api.middleware.idempotency import run_idempotent
from core.audit.log import append_in_txn
from core.errors import ConflictError, RebaseRequiredError, UngroundedError
from core.keys import DEFAULT_OWNER, DEFAULT_SPACE
from core.kv import WriteTxn
from core.repo import Repository
from core.runs.store import RunStore

router = APIRouter(prefix="/runs", tags=["runs"])


class ClaimModel(BaseModel):
    text: str
    quote: str
    source_ref: str


class WritePatch(BaseModel):
    path: str
    content: str


class CreateRunBody(BaseModel):
    space: str = Field(default=DEFAULT_SPACE)
    claims: list[ClaimModel]
    write: WritePatch | None = None


class VerdictBody(BaseModel):
    verdict: str
    message: str = "hitl publish"
    author: str = DEFAULT_OWNER
    expected_head: str | None = None


def _repo() -> Repository:
    return get_repository()


def _runs() -> RunStore:
    return RunStore(_repo().kv)


@router.post("")
def create_run(body: CreateRunBody) -> dict[str, Any]:
    repo = _repo()
    claims = [Claim(c.text, c.quote, c.source_ref) for c in body.claims]
    results = validate_claims(claims, repo.blobs)
    status = aggregate_status(results)
    if status == "blocked":
        raise HTTPException(
            status_code=422,
            detail={"error": "ungrounded", "validations": [r.__dict__ for r in results]},
        )

    run_id = _runs().create(
        {
            "space": body.space,
            "status": status,
            "claims": [c.__dict__ for c in claims],
            "validations": [r.__dict__ for r in results],
            "write": body.write.model_dump() if body.write else None,
            "verdict": None,
            "changeset_id": None,
        }
    )
    code = 200 if status == "ok" else 202
    return {"id": run_id, "status": status, "http_hint": code}


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
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail="Idempotency-Key обязателен")

    run = _runs().get(run_id)
    if run.get("status") == "blocked":
        raise UngroundedError("run blocked — вердикт невозможен")

    if body.verdict == "reject":
        updated = _runs().update(run_id, {"status": "rejected", "verdict": "reject"})
        return {"id": run_id, "status": updated["status"]}

    if body.verdict != "accept":
        raise HTTPException(status_code=422, detail="verdict: accept|reject")

    write = run.get("write")
    if not isinstance(write, dict):
        raise HTTPException(status_code=422, detail="run без write payload")

    space = str(run.get("space", DEFAULT_SPACE))
    repo = _repo()
    expected = body.expected_head.encode() if body.expected_head else repo.pointers.head(space)
    payload = {**body.model_dump(), "run_id": run_id, "write": write}

    path = str(write["path"])
    content = str(write["content"])

    def handler(txn: WriteTxn) -> tuple[int, dict[str, Any]]:
        blob_hash = repo.blobs.put_in_txn(txn, content.encode("utf-8"))
        repo.work.set_path_in_txn(txn, space, path, blob_hash)
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
        append_in_txn(
            txn,
            {
                "event": "hitl_publish",
                "run_id": run_id,
                "changeset_id": cs_id,
                "space": space,
            },
        )
        return 200, {"changeset_id": cs_id, "run_id": run_id, "status": "published"}

    result = run_idempotent(
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
    return result
