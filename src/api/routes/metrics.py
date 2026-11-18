from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from core import metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(metrics.render())
