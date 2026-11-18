from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from api.schemas import COMMON_RESPONSES
from core import metrics

router = APIRouter(tags=["metrics"], responses=COMMON_RESPONSES)


@router.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(metrics.render())
