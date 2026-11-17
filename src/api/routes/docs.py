from typing import Any

from fastapi import APIRouter, HTTPException

from api.deps import get_repository
from core.keys import DEFAULT_SPACE

router = APIRouter(prefix="/docs", tags=["docs"])


@router.get("/tree")
def get_tree(space: str = DEFAULT_SPACE) -> dict[str, Any]:
    repo = get_repository()
    head = repo.pointers.head(space)
    if head is None:
        return {"space": space, "head": None, "paths": {}}
    cs = repo.changesets.get(head.decode())
    paths = repo.blobs.read_tree(cs["tree_hash"])
    return {"space": space, "head": head.decode(), "paths": paths}


@router.get("/doc/{path:path}")
def get_doc(path: str, space: str = DEFAULT_SPACE) -> dict[str, Any]:
    repo = get_repository()
    head = repo.pointers.head(space)
    if head is None:
        raise HTTPException(status_code=404, detail="head не задан")
    cs = repo.changesets.get(head.decode())
    paths = repo.blobs.read_tree(cs["tree_hash"])
    blob_hash = paths.get(path)
    if blob_hash is None:
        raise HTTPException(status_code=404, detail="документ не найден")
    content = repo.blobs.read(blob_hash).decode("utf-8")
    return {"path": path, "blob_hash": blob_hash, "content": content}
