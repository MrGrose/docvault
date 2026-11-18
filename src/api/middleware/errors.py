from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.errors import (
    AuthzError,
    ConflictError,
    IdempotencyMismatchError,
    RebaseRequiredError,
    UngroundedError,
)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": "conflict", "detail": str(exc)},
        )

    @app.exception_handler(IdempotencyMismatchError)
    async def idem_mismatch(_request: Request, exc: IdempotencyMismatchError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": "idempotency_mismatch", "detail": str(exc)},
        )

    @app.exception_handler(RebaseRequiredError)
    async def rebase_handler(_request: Request, exc: RebaseRequiredError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": "rebase_required", "detail": str(exc)},
        )

    @app.exception_handler(UngroundedError)
    async def ungrounded_handler(_request: Request, exc: UngroundedError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "ungrounded", "detail": str(exc)},
        )

    @app.exception_handler(AuthzError)
    async def authz_handler(_request: Request, exc: AuthzError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"error": "authz", "detail": str(exc)},
        )
