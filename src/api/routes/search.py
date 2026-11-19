from fastapi import APIRouter, Query

from api.deps import get_repository
from api.schemas import COMMON_RESPONSES

router = APIRouter(tags=["search"], responses=COMMON_RESPONSES)


@router.get("/search")
def search(
    q: str,
    space: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    items = get_repository().search.search(q, space=space, limit=limit)
    return {"items": items}
