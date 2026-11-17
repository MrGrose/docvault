from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pytest_bdd import given, parsers, scenarios, then, when

from api.app import create_app
from api.deps import get_repository
from core.repo import Repository

scenarios("features/hitol.feature")

CONTEXT: dict[str, object] = {}


@pytest.fixture()
def bdd_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DOCVAULT_REPO", str(tmp_path / "bdd"))
    get_repository.cache_clear()
    Repository.init(tmp_path / "bdd")
    client = TestClient(create_app())
    CONTEXT.clear()
    CONTEXT["client"] = client
    return client


@given("an empty repository", target_fixture="bdd_env")
def empty_repository(bdd_env: TestClient) -> TestClient:
    return bdd_env


@given(parsers.parse('a source blob "{text}" as ref'))
def source_blob(text: str) -> None:
    repo = get_repository()
    blob_hash = repo.blobs.put(text.encode("utf-8"))
    CONTEXT["source_ref"] = f"blob:{blob_hash}"


@when(parsers.parse('I create a run claiming quote "{quote}"'))
def create_run_bad_quote(quote: str) -> None:
    client = CONTEXT["client"]
    assert isinstance(client, TestClient)
    body = {
        "claims": [
            {
                "text": "wrong tariff",
                "quote": quote,
                "source_ref": CONTEXT["source_ref"],
            }
        ],
        "write": {"path": "docs/t.md", "content": "x"},
    }
    CONTEXT["response"] = client.post("/runs", json=body)


@when("I create a run with unrelated claim text")
def create_run_weak() -> None:
    client = CONTEXT["client"]
    assert isinstance(client, TestClient)
    body = {
        "claims": [
            {
                "text": "quantum pricing model",
                "quote": "alpha beta",
                "source_ref": CONTEXT["source_ref"],
            }
        ],
        "write": {"path": "docs/t.md", "content": "published"},
    }
    resp = client.post("/runs", json=body)
    CONTEXT["response"] = resp
    CONTEXT["run_id"] = resp.json().get("id")


@when(parsers.parse('I accept the run with idempotency key "{key}"'))
def accept_run(key: str) -> None:
    client = CONTEXT["client"]
    assert isinstance(client, TestClient)
    run_id = str(CONTEXT["run_id"])
    CONTEXT["verdict"] = client.post(
        f"/runs/{run_id}/verdicts",
        json={"verdict": "accept"},
        headers={"Idempotency-Key": key},
    )


@then("the run is ungrounded")
def assert_ungrounded() -> None:
    resp = CONTEXT["response"]
    assert isinstance(resp, Response)
    assert resp.status_code == 422


@then("the run status is needs_human")
def assert_needs_human() -> None:
    resp = CONTEXT["response"]
    assert isinstance(resp, Response)
    assert resp.json()["status"] == "needs_human"


@then("the run is published")
def assert_published() -> None:
    resp = CONTEXT["verdict"]
    assert isinstance(resp, Response)
    assert resp.status_code == 200
    assert resp.json().get("changeset_id")
