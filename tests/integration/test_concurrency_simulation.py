import random
from pathlib import Path

from core.errors import ConflictError
from core.keys import DEFAULT_SPACE
from core.repo import Repository


def test_hundred_drafts_converge_without_lost_updates(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    try:
        pending: list[str] = []
        for i in range(100):
            draft = repo.drafts.create(DEFAULT_SPACE, "user:host", None)
            repo.write_draft(str(draft["id"]), f"docs/{i}.md", f"value {i}")
            pending.append(str(draft["id"]))

        rnd = random.Random(11)
        attempts = 0
        while pending:
            head = repo.pointers.head(DEFAULT_SPACE)
            progressed = False
            rnd.shuffle(pending)
            for draft_id in list(pending):
                draft = repo.drafts.get(draft_id)
                base = draft["base_head"].encode() if draft["base_head"] else None
                if base != head:
                    rebased = repo.rebase_draft(draft_id)
                    pending.remove(draft_id)
                    pending.append(str(rebased["id"]))
                    attempts += 1
                    continue
                try:
                    repo.publish_draft(draft_id, head, f"publish {draft_id[:6]}", "user:host")
                except ConflictError:
                    rebased = repo.rebase_draft(draft_id)
                    pending.remove(draft_id)
                    pending.append(str(rebased["id"]))
                    attempts += 1
                    continue
                pending.remove(draft_id)
                progressed = True
                attempts += 1
            if not progressed:
                raise AssertionError("публикации не продвигаются")

        log = repo.changesets.log(DEFAULT_SPACE)
        assert len(log) == 100
        head = repo.pointers.head(DEFAULT_SPACE)
        assert head is not None
        tree = repo.tree_at(head)
        assert len(tree) == 100
        for i in range(100):
            assert f"docs/{i}.md" in tree
    finally:
        repo.close()
