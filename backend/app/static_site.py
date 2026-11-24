"""Serve the built React app from the API server, so the whole project runs as one service.

Only used when ``frontend/dist`` exists (after ``npm run build``, or in the
Docker image). In development the Vite dev server serves the frontend instead.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def mount_frontend(app: FastAPI, dist: Path = None) -> bool:
    dist = Path(os.getenv("FRONTEND_DIST", dist or DEFAULT_DIST)).resolve()
    index = dist / "index.html"
    if not index.exists():
        return False
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def single_page_app(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist in candidate.parents:
            return FileResponse(candidate)
        # client-side routes such as /expenses are handled by React Router
        return FileResponse(index)

    return True
