from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.deps import get_repository
from api.schemas import COMMON_RESPONSES
from core.capability.revocation import RevocationStore
from core.capability.tokens import verify_token

router = APIRouter(prefix="/capability", tags=["capability"], responses=COMMON_RESPONSES)


class RevokeBody(BaseModel):
    token: str


@router.post("/revoke")
def revoke(body: RevokeBody) -> dict[str, object]:
    claims = verify_token(body.token)
    if not claims.jti:
        raise HTTPException(status_code=422, detail="token без jti нельзя отозвать")
    RevocationStore(get_repository().kv).revoke(claims.jti)
    return {"revoked": True, "jti": claims.jti}
