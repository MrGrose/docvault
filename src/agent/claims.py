import re
from dataclasses import dataclass
from typing import Literal

from core.storage.blob_store import BlobStore

ValidationStatus = Literal["grounded", "blocked", "needs_human"]


@dataclass(frozen=True)
class Claim:
    text: str
    quote: str
    source_ref: str
    path: str = ""
    change_kind: str = "add"
    byte_range: tuple[int, int] | None = None


@dataclass(frozen=True)
class ClaimValidation:
    status: ValidationStatus
    reason: str
    evidence: str = "skipped"
    binding: str = "skipped"
    support: str = "skipped"


def _blob_hash_from_ref(source_ref: str) -> str:
    if source_ref.startswith("blob:"):
        return source_ref.removeprefix("blob:")
    return source_ref


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split())


def check_evidence_integrity(claim: Claim, blobs: BlobStore) -> ClaimValidation:
    try:
        blob_hash = _blob_hash_from_ref(claim.source_ref)
        data = blobs.read(blob_hash)
    except (KeyError, ValueError) as exc:
        return ClaimValidation(
            "blocked",
            f"source_ref недоступен: {exc}",
            evidence="blocked",
        )

    quote_bytes = claim.quote.encode("utf-8")
    if claim.byte_range is not None:
        start, end = claim.byte_range
        if start < 0 or end < start or end > len(data):
            return ClaimValidation(
                "blocked",
                "byte_range вне источника",
                evidence="blocked",
            )
        if data[start:end] != quote_bytes:
            return ClaimValidation(
                "blocked",
                "цитата не совпала с byte_range",
                evidence="blocked",
            )
    elif quote_bytes not in data:
        return ClaimValidation(
            "blocked",
            "цитата не найдена в source (fabricated quote)",
            evidence="blocked",
        )

    return ClaimValidation("grounded", "evidence ok", evidence="ok")


def _paragraphs(text: str) -> list[str]:
    return [part for part in re.split(r"\n\s*\n", text) if part.strip()]


def changed_fragments(old: str, new: str) -> tuple[list[str], list[str]]:
    old_norm = {normalize_text(part) for part in _paragraphs(old)}
    new_norm = {normalize_text(part) for part in _paragraphs(new)}
    added = [part for part in _paragraphs(new) if normalize_text(part) not in old_norm]
    removed = [part for part in _paragraphs(old) if normalize_text(part) not in new_norm]
    return added, removed


def check_change_binding(claim: Claim, old: str, new: str) -> tuple[str, str]:
    if not claim.path:
        return "needs_human", "claim без path"
    added, removed = changed_fragments(old, new)
    text = normalize_text(claim.text)
    if not text:
        return "needs_human", "пустой claim text"
    if claim.change_kind == "delete":
        removed_text = [normalize_text(part) for part in removed]
        if text in removed_text and text not in normalize_text(new):
            return "ok", "binding к удаленному фрагменту"
        return "needs_human", "claim не связан с удаленным фрагментом"
    for part in added:
        if text in normalize_text(part):
            return "ok", "binding к измененному фрагменту"
    return "needs_human", "claim не связан с измененным фрагментом"


def check_claim_support(claim: Claim, evidence_ok: bool) -> ClaimValidation:
    if not evidence_ok:
        return ClaimValidation(
            "blocked",
            "evidence integrity failed",
            evidence="blocked",
        )

    text_tokens = {t for t in re.findall(r"\w+", claim.text.lower()) if len(t) > 2}
    quote_tokens = {t for t in re.findall(r"\w+", claim.quote.lower()) if len(t) > 2}
    if not text_tokens:
        return ClaimValidation(
            "needs_human",
            "пустой claim text",
            evidence="ok",
            support="weak",
        )
    if not (text_tokens & quote_tokens):
        return ClaimValidation(
            "needs_human",
            "нет пересечения ключевых токенов text/quote, нужна проверка человеком",
            evidence="ok",
            support="weak",
        )
    return ClaimValidation("grounded", "support hint ok", evidence="ok", support="ok")


def validate_claim(claim: Claim, blobs: BlobStore) -> ClaimValidation:
    evidence = check_evidence_integrity(claim, blobs)
    if evidence.status == "blocked":
        return evidence
    return check_claim_support(claim, evidence_ok=True)


def validate_claim_for_change(
    claim: Claim,
    old: str,
    new: str,
    blobs: BlobStore,
) -> ClaimValidation:
    evidence = check_evidence_integrity(claim, blobs)
    if evidence.status == "blocked":
        return evidence
    binding, binding_reason = check_change_binding(claim, old, new)
    support = check_claim_support(claim, evidence_ok=True)
    if binding != "ok":
        return ClaimValidation(
            "needs_human",
            binding_reason,
            evidence="ok",
            binding=binding,
            support=support.support,
        )
    if support.support != "ok":
        return ClaimValidation(
            "needs_human",
            support.reason,
            evidence="ok",
            binding="ok",
            support="weak",
        )
    return ClaimValidation(
        "grounded",
        "evidence, binding и support hint пройдены; смысл проверяет человек",
        evidence="ok",
        binding="ok",
        support="ok",
    )
