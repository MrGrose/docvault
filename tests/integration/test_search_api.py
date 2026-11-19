from typing import Any

from api.deps import get_repository
from cli.dv import main


def test_search_finds_published_document(api: Any) -> None:
    draft = api.draft()
    api.write_ok(
        draft["id"],
        "docs/tariffs.md",
        "# Тарифы\n\nBasic: 100 рублей в месяц.\n",
        "w-search",
    )
    api.publish_ok(draft["id"], None, "p-search")

    found = api.client.get("/search", params={"q": "тариф"})
    assert found.status_code == 200
    items = found.json()["items"]
    assert len(items) == 1
    assert items[0]["space"] == "default"
    assert items[0]["path"] == "docs/tariffs.md"
    assert "Тариф" in items[0]["snippet"]

    assert api.client.get("/search", params={"q": "тариф", "space": "other"}).json()["items"] == []
    assert api.client.get("/search", params={"q": "missing"}).json()["items"] == []


def test_search_rebuild_cli(api: Any, capsys: Any) -> None:
    draft = api.draft()
    api.write_ok(draft["id"], "docs/a.md", "hello rebuild", "w-rebuild")
    api.publish_ok(draft["id"], None, "p-rebuild")
    path = str(get_repository().root)
    assert main(["--path", path, "search-rebuild"]) == 0
    assert "проиндексировано документов: 1" in capsys.readouterr().out
