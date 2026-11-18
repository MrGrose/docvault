import hmac
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.middleware.errors import register_error_handlers
from api.routes import audit, capability, changesets, docs, runs

UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="docvault", version="0.1.0")
    register_error_handlers(app)
    app.include_router(changesets.router)
    app.include_router(docs.router)
    app.include_router(runs.router)
    app.include_router(audit.router)
    app.include_router(capability.router)
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
                return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
