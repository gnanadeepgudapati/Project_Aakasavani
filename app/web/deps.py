"""FastAPI dependencies. Kept separate from main.py/routes.py so tests can
import get_db and override it (app.dependency_overrides[get_db] = ...)
without circular imports.
"""

from __future__ import annotations

import os
from pathlib import Path

from app import db as db_module

DEFAULT_DB_PATH = Path(
    os.environ.get(
        "AAKASAVANI_DB_PATH",
        str(Path(__file__).resolve().parent.parent.parent / "aakasavani.db"),
    )
)


def get_db():
    conn = db_module.connect(DEFAULT_DB_PATH)
    db_module.migrate(conn)
    try:
        yield conn
    finally:
        conn.close()
