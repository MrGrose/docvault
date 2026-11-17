import threading
from pathlib import Path

from core.errors import ConflictError
from core.keys import DEFAULT_SPACE
from core.repo import Repository


def _commit_worker(
    repo_path: Path,
    expected_head: bytes,
    results: list[str | BaseException],
) -> None:
    repo = Repository.open(repo_path)
    try:
        blob = repo.blobs.put(b"data")
        repo.work.set_path(DEFAULT_SPACE, "f.txt", blob)
        cs_id = repo.changesets.commit_working_copy(
            DEFAULT_SPACE,
            message="parallel",
            author="t",
            expected_head=expected_head,
        )
        results.append(cs_id)
    except Exception as exc:
        results.append(exc)
    finally:
        repo.close()


def test_two_parallel_commits_one_conflict(tmp_path: Path) -> None:
    repo_path = tmp_path / "r"
    seed = Repository.init(repo_path)
    seed_blob = seed.blobs.put(b"seed")
    seed.work.set_path(DEFAULT_SPACE, "seed.txt", seed_blob)
    parent_head = seed.changesets.commit_working_copy(
        DEFAULT_SPACE,
        message="seed",
        author="seed",
        expected_head=None,
    )
    seed.close()

    expected = parent_head.encode()
    results: list[str | BaseException] = []
    t1 = threading.Thread(target=_commit_worker, args=(repo_path, expected, results))
    t2 = threading.Thread(target=_commit_worker, args=(repo_path, expected, results))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
    successes = [r for r in results if isinstance(r, str)]
    conflicts = [r for r in results if isinstance(r, ConflictError)]
    assert len(successes) == 1
    assert len(conflicts) == 1
