from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.middleware.errors import register_error_handlers
from api.routes import audit, changesets, docs, runs

UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="docvault", version="0.1.0")
    register_error_handlers(app)
    app.include_router(changesets.router)
    app.include_router(docs.router)
    app.include_router(runs.router)
    app.include_router(audit.router)
    if UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
