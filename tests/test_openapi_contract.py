import json
from pathlib import Path

from api.app import create_app


def test_committed_openapi_matches_app() -> None:
    expected = create_app().openapi()
    actual = json.loads(Path("openapi.json").read_text(encoding="utf-8"))
    assert actual == expected


def test_openapi_documents_bearer_auth() -> None:
    spec = create_app().openapi()
    assert spec["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert spec["paths"]["/changesets"]["get"]["security"] == [{"BearerAuth": []}, {}]
