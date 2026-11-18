from typing import Any

from fastapi import APIRouter, Query

from api.deps import get_repository
from api.schemas import COMMON_RESPONSES
from core.audit.log import list_records

router = APIRouter(prefix="/audit", tags=["audit"], responses=COMMON_RESPONSES)


@router.get("")
def get_audit(
    from_seq: int = 0,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    repo = get_repository()
    records = list_records(repo.kv, from_seq=from_seq, limit=limit)
    return {"from_seq": from_seq, "records": records}
