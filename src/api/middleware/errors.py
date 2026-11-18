from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = jsonable_encoder(exc.errors())
        for error in errors:
            if "Idempotency-Key" in str(error.get("loc", "")):
                return JSONResponse(
                    status_code=422,
                    content={"error": "validation", "detail": "Idempotency-Key обязателен"},
                )
        return JSONResponse(
            status_code=422,
            content={"error": "validation", "detail": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": codes.get(exc.status_code, "error"), "detail": exc.detail},
            headers=exc.headers,
        )
