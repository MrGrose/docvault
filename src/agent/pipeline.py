import os
from collections.abc import Callable

from agent.claims import Claim, ClaimValidation
from agent.llm import openrouter
from agent.stages.draft import draft_tariffs_code
from agent.stages.draft_llm import draft_with_llm
from agent.stages.validate import aggregate_status, validate_claims
from core.storage.blob_store import BlobStore

Client = Callable[[str], str]


def run_draft_stage(
    task: str,
    source: str = "",
    client: Client | None = None,
    instruction: str = "",
) -> str:
    if task != "update_tariffs":
        msg = f"неизвестная задача: {task}"
        raise ValueError(msg)
    if os.environ.get("DOCVAULT_LLM", "template") == "openrouter":
        chosen = client if client is not None else openrouter.complete
        return draft_with_llm(task, source, client=chosen, instruction=instruction)
    return draft_tariffs_code()


def run_pipeline(
    task: str,
    source: str = "",
    client: Client | None = None,
    instruction: str = "",
) -> str:
    return run_draft_stage(task, source, client=client, instruction=instruction)


def validation_status_for_claims(
    claims: list[Claim],
    blobs: BlobStore,
) -> tuple[str, list[ClaimValidation]]:
    results = validate_claims(claims, blobs)
    return aggregate_status(results), results
