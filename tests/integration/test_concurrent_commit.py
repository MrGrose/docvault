import threading
from pathlib import Path

from core.errors import RebaseRequiredError
from core.keys import DEFAULT_SPACE
from core.repo import Repository


def _seed(repo_path: Path) -> bytes:
    repo = Repository.init(repo_path)
    draft = repo.drafts.create(DEFAULT_SPACE, "user:host", None)
    repo.write_draft(str(draft["id"]), "seed.txt", "seed")
    cs_id = repo.publish_draft(str(draft["id"]), None, "seed", "user:host")
    head = cs_id.encode()
    repo.close()
    return head


def _publish_worker(
    repo_path: Path,
    draft_id: str,
    base_head: bytes,
    out: list[object],
) -> None:
    repo = Repository.open(repo_path)
    try:
        cs_id = repo.publish_draft(draft_id, base_head, "parallel", "user:host")
        out.append(cs_id)
    except Exception as exc:
        out.append(exc)
    finally:
        repo.close()


def test_two_drafts_one_path_one_conflict(tmp_path: Path) -> None:
    repo_path = tmp_path / "r"
    base = _seed(repo_path)

    repo = Repository.open(repo_path)
    first = repo.drafts.create(DEFAULT_SPACE, "user:host", base)
    second = repo.drafts.create(DEFAULT_SPACE, "user:host", base)
    repo.write_draft(str(first["id"]), "f.txt", "first")
    repo.write_draft(str(second["id"]), "f.txt", "second")
    repo.close()

    results: list[object] = []
    t1 = threading.Thread(target=_publish_worker, args=(repo_path, str(first["id"]), base, results))
    t2 = threading.Thread(
        target=_publish_worker, args=(repo_path, str(second["id"]), base, results)
    )
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [r for r in results if isinstance(r, str)]
    conflicts = [r for r in results if isinstance(r, RebaseRequiredError)]
    assert len(successes) == 1
    assert len(conflicts) == 1


def test_rebase_then_publish_keeps_both_edits(tmp_path: Path) -> None:
    repo_path = tmp_path / "r"
    base = _seed(repo_path)

    repo = Repository.open(repo_path)
    first = repo.drafts.create(DEFAULT_SPACE, "user:host", base)
    second = repo.drafts.create(DEFAULT_SPACE, "user:host", base)
    repo.write_draft(str(first["id"]), "one.txt", "one")
    repo.write_draft(str(second["id"]), "two.txt", "two")
    repo.publish_draft(str(first["id"]), base, "first", "user:host")
    head = repo.pointers.head(DEFAULT_SPACE)
    rebased = repo.rebase_draft(str(second["id"]))
    cs_id = repo.publish_draft(str(rebased["id"]), head, "second", "user:host")
    tree = repo.tree_at(cs_id)
    assert "one.txt" in tree
    assert "two.txt" in tree
    repo.close()
