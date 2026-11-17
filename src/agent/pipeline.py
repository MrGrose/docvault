from agent.claims import Claim, ClaimValidation
from agent.stages.draft import draft_tariffs_code
from agent.stages.validate import aggregate_status, validate_claims
from core.storage.blob_store import BlobStore


def run_draft_stage(task: str) -> str:
    if task == "update_tariffs":
        return draft_tariffs_code()
    msg = f"неизвестная задача: {task}"
    raise ValueError(msg)


def run_pipeline(task: str) -> str:
    return run_draft_stage(task)


def validation_status_for_claims(
    claims: list[Claim],
    blobs: BlobStore,
) -> tuple[str, list[ClaimValidation]]:
    results = validate_claims(claims, blobs)
    return aggregate_status(results), results
