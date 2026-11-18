import argparse
import shutil
import tempfile
import threading
import time
from pathlib import Path

from core.errors import RebaseRequiredError
from core.repo import Repository


def worker(repo: Repository, index: int, result: dict[str, int], lock: threading.Lock) -> None:
    path = f"docs/file-{index:04d}.md"
    attempts = 0
    while True:
        attempts += 1
        base = repo.pointers.head("default")
        draft = repo.drafts.create("default", "bench", base)
        draft_id = str(draft["id"])
        repo.write_draft(draft_id, path, f"content {index}\n")
        try:
            repo.publish_draft(draft_id, base, f"write {index}", "bench", source="bench")
            break
        except RebaseRequiredError:
            result["conflicts"] += 1
        if attempts > 50:
            result["failed"] += 1
            return
    result["published"] += 1
    with lock:
        result["attempts"] += attempts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--writers", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    root = Path(tempfile.mkdtemp(prefix="docvault-writers-"))
    repo = Repository.init(root)
    result: dict[str, int] = {"published": 0, "conflicts": 0, "failed": 0, "attempts": 0}
    lock = threading.Lock()
    started = time.perf_counter()
    threads = [
        threading.Thread(
            target=worker,
            args=(repo, index, result, lock),
            daemon=True,
        )
        for index in range(args.writers)
    ]
    for offset in range(0, len(threads), args.workers):
        batch = threads[offset : offset + args.workers]
        for thread in batch:
            thread.start()
        for thread in batch:
            thread.join()
    elapsed = time.perf_counter() - started

    head = repo.pointers.head("default")
    tree = repo.tree_at(head.decode()) if head else {}
    history = len(repo.changesets.log("default"))
    repo.close()
    shutil.rmtree(root, ignore_errors=True)
    print(
        f"writers={args.writers} published={result['published']} failed={result['failed']} "
        f"conflicts={result['conflicts']} attempts={result['attempts']} "
        f"tree={len(tree)} history={history} seconds={elapsed:.2f}"
    )
    return 0 if result["failed"] == 0 and len(tree) == args.writers else 1


if __name__ == "__main__":
    raise SystemExit(main())
