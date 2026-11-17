import re
from dataclasses import dataclass
from typing import Literal

from core.storage.blob_store import BlobStore

ValidationStatus = Literal["ok", "blocked", "needs_human"]


@dataclass(frozen=True)
class Claim:
    text: str
    quote: str
    source_ref: str


@dataclass(frozen=True)
class ClaimValidation:
    status: ValidationStatus
    reason: str


def _blob_hash_from_ref(source_ref: str) -> str:
    if source_ref.startswith("blob:"):
        return source_ref.removeprefix("blob:")
    return source_ref


def check_evidence_integrity(claim: Claim, blobs: BlobStore) -> ClaimValidation:
    try:
        blob_hash = _blob_hash_from_ref(claim.source_ref)
        data = blobs.read(blob_hash)
    except (KeyError, ValueError) as exc:
        return ClaimValidation("blocked", f"source_ref недоступен: {exc}")

    quote_bytes = claim.quote.encode("utf-8")
    if quote_bytes not in data:
        return ClaimValidation("blocked", "цитата не найдена в source (fabricated quote)")

    return ClaimValidation("ok", "evidence integrity ok")


def check_claim_support(claim: Claim, evidence_ok: bool) -> ClaimValidation:
    if not evidence_ok:
        return ClaimValidation("blocked", "evidence integrity failed")

    text_tokens = {t for t in re.findall(r"\w+", claim.text.lower()) if len(t) > 2}
    quote_tokens = {t for t in re.findall(r"\w+", claim.quote.lower()) if len(t) > 2}
    if not text_tokens:
        return ClaimValidation("needs_human", "пустой claim text")
    overlap = text_tokens & quote_tokens
    if not overlap:
        return ClaimValidation(
            "needs_human",
            "нет пересечения ключевых токенов text/quote (claim support не проверен)",
        )
    return ClaimValidation("ok", "claim support heuristic ok")


def validate_claim(claim: Claim, blobs: BlobStore) -> ClaimValidation:
    evidence = check_evidence_integrity(claim, blobs)
    if evidence.status == "blocked":
        return evidence
    return check_claim_support(claim, evidence_ok=True)
