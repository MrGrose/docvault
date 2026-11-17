from agent.claims import Claim, ClaimValidation, validate_claim
from core.storage.blob_store import BlobStore


def validate_claims(claims: list[Claim], blobs: BlobStore) -> list[ClaimValidation]:
    return [validate_claim(c, blobs) for c in claims]


def aggregate_status(results: list[ClaimValidation]) -> str:
    if any(r.status == "blocked" for r in results):
        return "blocked"
    if any(r.status == "needs_human" for r in results):
        return "needs_human"
    return "ok"
