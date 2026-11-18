from pathlib import Path

from core.keys import DEFAULT_SPACE
from core.repo import Repository


def test_many_serial_publishes_keep_history(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        for i in range(50):
            head = repo.pointers.head(DEFAULT_SPACE)
            draft = repo.drafts.create(DEFAULT_SPACE, "user:host", head)
            repo.write_draft(str(draft["id"]), f"docs/{i}.md", f"v{i}")
            repo.publish_draft(str(draft["id"]), head, f"step {i}", "user:host")
        log = repo.changesets.log(DEFAULT_SPACE)
        assert len(log) == 50
        assert log[0]["message"] == "step 49"
        assert log[-1]["message"] == "step 0"
        head = repo.pointers.head(DEFAULT_SPACE)
        assert head is not None
        tree = repo.tree_at(head)
        assert len(tree) == 50
    finally:
        repo.close()
