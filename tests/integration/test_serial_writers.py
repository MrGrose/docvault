from pathlib import Path

from core.keys import DEFAULT_SPACE
from core.repo import Repository


def test_serial_commits_no_lost_updates(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo = Repository.init(repo_path)
    ids: list[str] = []
    for i in range(50):
        blob = repo.blobs.put(f"version-{i}".encode())
        repo.work.set_path(DEFAULT_SPACE, "doc.txt", blob)
        head = repo.pointers.head(DEFAULT_SPACE)
        cs_id = repo.changesets.commit_working_copy(
            DEFAULT_SPACE,
            message=f"commit-{i}",
            author="writer",
            expected_head=head,
        )
        ids.append(cs_id)
    log = repo.changesets.log(DEFAULT_SPACE)
    assert len(log) == 50
    assert len(ids) == len(set(ids))
    repo.close()
