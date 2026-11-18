import threading
from pathlib import Path

from core.errors import RebaseRequiredError
from core.repo import Repository


def _writer(repo: Repository, index: int, result: dict[str, int], lock: threading.Lock) -> None:
    path = f"docs/file-{index:03d}.md"
    for _ in range(50):
        base = repo.pointers.head("default")
        draft = repo.drafts.create("default", "test", base)
        draft_id = str(draft["id"])
        repo.write_draft(draft_id, path, f"content {index}\n")
        try:
            repo.publish_draft(draft_id, base, f"write {index}", "test")
            with lock:
                result["published"] += 1
            return
        except RebaseRequiredError:
            with lock:
                result["conflicts"] += 1
    with lock:
        result["failed"] += 1


def test_hundred_writers_do_not_lose_updates(tmp_path: Path) -> None:
    repo = Repository.init(tmp_path / "repo")
    result: dict[str, int] = {"published": 0, "conflicts": 0, "failed": 0}
    lock = threading.Lock()
    threads = [
        threading.Thread(target=_writer, args=(repo, index, result, lock), daemon=True)
        for index in range(100)
    ]
    for offset in range(0, len(threads), 8):
        batch = threads[offset : offset + 8]
        for thread in batch:
            thread.start()
        for thread in batch:
            thread.join()

    head = repo.pointers.head("default")
    assert head is not None
    tree = repo.tree_at(head.decode())
    history = repo.changesets.log("default")
    assert result == {"published": 100, "conflicts": result["conflicts"], "failed": 0}
    assert len(tree) == 100
    assert len(history) == 100
    repo.close()
