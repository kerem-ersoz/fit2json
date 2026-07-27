"""FastAPI application factory for the FitSift web app.

Mounts the JSON API under ``/api`` and (optionally) serves the built React SPA,
falling back to ``index.html`` for client-side routes. ``base_path`` maps to FastAPI's
``root_path`` so the app can later be served under a prefix (e.g. ``/fitsift``) behind a
reverse proxy without code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fit2json import __version__
from fit2json.web import BRAND_NAME
from fit2json.web.config import get_settings
from fit2json.web.routes import activities, analyze, ingest, memory, meta, profile


def create_app() -> FastAPI:
    settings = get_settings()
    root_path = "" if settings.base_path == "/" else settings.base_path.rstrip("/")

    app = FastAPI(title=f"{BRAND_NAME} API", version=__version__, root_path=root_path)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(meta.router, prefix="/api")
    app.include_router(activities.router, prefix="/api")
    app.include_router(analyze.router, prefix="/api")
    app.include_router(memory.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")
    app.include_router(profile.router, prefix="/api")

    _mount_spa(app, settings.frontend_dist)
    return app


def _mount_spa(app: FastAPI, dist: Optional[Path]) -> None:
    """Serve the built SPA if present, with an index.html fallback for client routes."""
    if not dist:
        return
    dist = Path(dist)
    if not (dist / "index.html").exists():
        return

    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    index_file = dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # Never let the SPA fallback swallow API / docs routes.
        if full_path.startswith(("api", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(index_file))


app = create_app()
