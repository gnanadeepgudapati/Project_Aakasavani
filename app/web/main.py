"""FastAPI app object. ARCHITECTURE.md §6: "app process - FastAPI: web +
scheduler + IA queue worker" - this module is the web half.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Aakasavani")

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from app.web.research_routes import router as research_router  # noqa: E402
from app.web.routes import router  # noqa: E402

app.include_router(router)
app.include_router(research_router)
