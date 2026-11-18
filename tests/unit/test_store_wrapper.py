from pathlib import Path

from core.store import Store


def test_store_opens_empty_directory_and_initializes(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    store = Store.open(root)
    try:
        assert store.root == root
        assert store.repo.root == root
        store.init_repo()
        assert (root / ".docvault").exists()
    finally:
        store.close()


def test_store_opens_initialized_repository(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    first = Store.open(root)
    first.init_repo()
    first.close()

    second = Store.open(root)
    try:
        assert (root / ".docvault").exists()
        assert second.repo.pointers.head("default") is None
    finally:
        second.close()
