import hmac
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.middleware.errors import register_error_handlers
from api.routes import audit, capability, changesets, docs, metrics, runs, search

UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="docvault", version="0.1.0")
    register_error_handlers(app)
    app.include_router(changesets.router)
    app.include_router(docs.router)
    app.include_router(runs.router)
    app.include_router(audit.router)
    app.include_router(capability.router)
    app.include_router(metrics.router)
    app.include_router(search.router)
    if UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

    public = ("/health", "/ui", "/docs", "/redoc", "/openapi.json")

    @app.middleware("http")
    async def require_api_token(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        token = os.environ.get("DOCVAULT_API_TOKEN", "")
        if token and not request.url.path.startswith(public):
            header = request.headers.get("authorization", "")
            supplied = header[7:] if header.lower().startswith("bearer ") else ""
            if not hmac.compare_digest(supplied, token):
                return JSONResponse(
                    status_code=401,
                    content={"error": "unauthorized", "detail": "unauthorized"},
                )
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        components = schema.setdefault("components", {})
        components["securitySchemes"] = {"BearerAuth": {"type": "http", "scheme": "bearer"}}
        for item in schema.get("paths", {}).values():
            for operation in item.values():
                if isinstance(operation, dict):
                    operation["security"] = [{"BearerAuth": []}, {}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app
