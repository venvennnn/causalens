from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, frontend_dir: str) -> None:
    root = Path(frontend_dir).expanduser().resolve() if frontend_dir else None
    index = root / "index.html" if root else None
    if not root or not index or not index.is_file():

        @app.get("/")
        def api_root() -> dict:
            return {"service": "causalens-sea", "health": "/health", "docs": "/docs"}

        return

    next_dir = root / "_next"
    if next_dir.is_dir():
        app.mount("/_next", StaticFiles(directory=str(next_dir)), name="next-assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(index)

    favicon = root / "favicon.ico"
    if favicon.is_file():

        @app.get("/favicon.ico")
        def spa_favicon() -> FileResponse:
            return FileResponse(favicon)
