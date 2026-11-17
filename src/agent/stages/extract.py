from typing import Any

from core.repo import Repository


def extract_provenance(repo: Repository, space: str, doc_path: str) -> list[dict[str, Any]]:
    head = repo.pointers.head(space)
    if head is None:
        return []
    cs = repo.changesets.get(head.decode())
    paths = repo.blobs.read_tree(cs["tree_hash"])
    blob_hash = paths.get(doc_path)
    if blob_hash is None:
        return []
    chunks = repo.blobs.chunk_hashes(blob_hash)
    return [{"path": doc_path, "blob_hash": blob_hash, "chunk_hashes": chunks}]
