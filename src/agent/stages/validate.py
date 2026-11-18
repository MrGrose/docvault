from agent.claims import Claim, ClaimValidation, validate_claim, validate_claim_for_change
from core.storage.blob_store import BlobStore


def validate_claims(claims: list[Claim], blobs: BlobStore) -> list[ClaimValidation]:
    return [validate_claim(c, blobs) for c in claims]


def validate_claims_for_change(
    claims: list[Claim],
    documents: dict[str, tuple[str, str]],
    blobs: BlobStore,
) -> list[ClaimValidation]:
    results: list[ClaimValidation] = []
    for claim in claims:
        if claim.path not in documents:
            results.append(validate_claim_for_change(claim, "", "", blobs))
            continue
        old, new = documents[claim.path]
        results.append(validate_claim_for_change(claim, old, new, blobs))
    return results


def aggregate_status(results: list[ClaimValidation]) -> str:
    if any(r.status == "blocked" for r in results):
        return "blocked"
    if any(r.status == "needs_human" for r in results):
        return "needs_human"
    return "grounded"
